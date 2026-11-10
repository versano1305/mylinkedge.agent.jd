"""Legacy node implementations pending per-folder migration."""

from __future__ import annotations

import time
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.event_hub import (
    CompanyLookup,
    CompanyLookupResult,
    EventProcessingStatus,
    EventStatusClient,
    GraphId,
    HubPublisher,
    UnresolvedNode,
)
from mylinkedge_agent_tools.event_hub.lookup import CompanyLookupPayload
from mylinkedge_agent_tools.langgraph_streaming.annotations import thinking
from mylinkedge_agent_tools.langgraph_streaming.custom_events import (
    emit_client_event,
    emit_finish_interview,
)

from jd_agent.graphs.jd_extract.state import JdExtractState
from jd_agent.graphs.jd_extract.tools import fetch_job_posting_impl
from jd_agent.integrations.supabase.jd_repository import (
    URL_ORIGIN_TYPES,
    JobDescription,
)
from jd_agent.shared.jd_event_hub import publish_jd_extraction_end_from_state

_COMPANY_LOOKUP_TIMEOUT_SECONDS = 120.0
_COMPANY_LOOKUP_STATUS_HTTP_TIMEOUT_SECONDS = 30.0
_COMPANY_LOOKUP_POLL_INTERVAL_SECONDS = 1.0


def _non_empty_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _run_id_from_config(config: RunnableConfig | None) -> str | None:
    if not isinstance(config, dict):
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None
    return _non_empty_str(configurable.get("run_id")) or _non_empty_str(
        configurable.get("thread_id")
    )


def _require_jd(state: JdExtractState) -> JobDescription:
    jd = state.get("jd")
    if not isinstance(jd, JobDescription):
        raise ValueError("jd is required")
    return jd


def route_by_origin_type(
    state: JdExtractState,
) -> Literal["fetch_jd", "prepare_jd_text"]:
    """Route URL origins through fetch_jd; copy_paste goes to prepare_jd_text."""
    jd = _require_jd(state)
    if jd.origin_type in URL_ORIGIN_TYPES:
        return "fetch_jd"
    return "prepare_jd_text"


@thinking("Fetching job posting from URL…")
def fetch_jd(state: JdExtractState) -> dict[str, Any]:
    """Fetch JD content from a job-board URL via the retrieval tool.

    Reads the URL from ``jd.origin_jd`` and maps ``jd.origin_type`` to a
    fetch source. Writes normalized text to ``jd_text`` and fills
    ``company_name`` / ``title_name`` on ``jd`` when they are empty.
    """
    jd = _require_jd(state)
    url = (jd.origin_jd or "").strip()
    origin_type = (jd.origin_type or "").strip()

    # Map DB origin_type → fetch_job_posting source hint.
    if origin_type == "linkedin_url":
        source = "linkedin"
    else:
        source = origin_type.removesuffix("_url") or "linkedin"

    posting = fetch_job_posting_impl(url, source)

    updates: dict[str, Any] = {"jd_text": posting.description}
    name_updates: dict[str, str] = {}
    if not (jd.company_name or "").strip() and posting.company_name:
        name_updates["company_name"] = posting.company_name
    if not (jd.title_name or "").strip() and posting.title:
        name_updates["title_name"] = posting.title
    if name_updates:
        updates["jd"] = jd.model_copy(update=name_updates)
    return updates


@thinking("Resolving company…")
def resolve_company(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Publish ``company_lookup`` and poll hub status until a company id returns."""
    jd = _require_jd(state)
    company_name = (jd.company_name or "").strip()
    if not company_name:
        raise ValueError("company_name is required before resolve_company")

    jd_id = _non_empty_str(state.get("jd_id")) or _non_empty_str(jd.id)
    context: dict[str, Any] = {}
    if jd_id:
        context["job_description_id"] = jd_id
        context["job_id"] = _non_empty_str(state.get("job_id")) or jd_id
    run_id = _run_id_from_config(config)
    if run_id:
        context["run_id"] = run_id

    event = CompanyLookup(
        initiator=GraphId.JD_EXTRACT,
        user_id=_non_empty_str(state.get("user_id")),
        payload=CompanyLookupPayload(
            nodes=[UnresolvedNode(label="Company", name=company_name)],
            context=context,
        ),
    )
    publisher = HubPublisher(
        status_client=EventStatusClient(timeout=_COMPANY_LOOKUP_STATUS_HTTP_TIMEOUT_SECONDS),
    )
    publisher.publish(event)

    deadline = time.monotonic() + _COMPANY_LOOKUP_TIMEOUT_SECONDS
    current = publisher.get_status(event.id)
    while current is None or not current.is_terminal:
        if time.monotonic() >= deadline:
            last = current.status if current is not None else "unknown"
            raise TimeoutError(
                f"company_lookup {event.id} did not finish in time (last status: {last})"
            )
        time.sleep(_COMPANY_LOOKUP_POLL_INTERVAL_SECONDS)
        current = publisher.get_status(event.id)

    if current.status != EventProcessingStatus.SUCCEEDED:
        detail = current.error.message if current.error else current.status
        raise RuntimeError(f"company_lookup {event.id} failed: {detail}")

    result = current.result_as(CompanyLookupResult)
    if result is None or not result.resolved:
        raise ValueError(f"company_lookup could not resolve company_name={company_name!r}")

    company_id = (result.resolved[0].id or "").strip()
    if not company_id:
        raise ValueError(
            f"company_lookup resolved {company_name!r} without a company id"
        )
    return {"company_id": company_id}


@thinking("Finishing JD extraction…")
def mark_done(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Publish ``JD_EXTRACTION_END`` and signal completion to stream clients."""
    jd = _require_jd(state)
    jd_id = str(state.get("jd_id") or jd.id).strip()
    if not jd_id:
        raise ValueError("jd_id is required")

    skills = [skill.model_dump() for skill in jd.skills]
    sections = dict(jd.sections)
    publish_jd_extraction_end_from_state(
        state,
        skills=skills,
        sections=sections,
        config=config,
    )
    emit_client_event(
        "jd_extraction_finish",
        {
            "job_description_id": jd_id,
            "skills": skills,
            "sections": sections,
        },
    )
    emit_finish_interview()
    return {"extraction_status": "done"}

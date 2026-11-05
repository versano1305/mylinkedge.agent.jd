"""Legacy node implementations pending per-folder migration."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
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
from jd_agent.shared.jd_event_hub import (
    publish_company_lookup_from_state,
    publish_jd_extraction_end_from_state,
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
    """Publish ``COMPANY_LOOKUP`` for ``jd.company_name``.

    The company id is resolved downstream from the lookup result.
    """
    jd = _require_jd(state)
    company_name = (jd.company_name or "").strip()
    if not company_name:
        raise ValueError("company_name is required before resolve_company")
    publish_company_lookup_from_state(
        state,
        company_name=company_name,
        config=config,
    )
    return {}


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

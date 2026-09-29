"""Legacy node implementations pending per-folder migration."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.event_hub import (
    JdExtractionFinish,
    JdExtractionFinishPayload,
    JdExtractionStarted,
    ProcessEventPublisher,
)

from jd_agent.graphs.jd_extract.state import JdExtractState
from jd_agent.graphs.jd_extract.tools import (
    fetch_job_posting_impl,
    resolve_company_id,
)
from jd_agent.integrations.supabase import jd_repository as jd_repo
from jd_agent.integrations.supabase.client import client_from_env
from jd_agent.integrations.supabase.jd_repository import (
    URL_ORIGIN_TYPES,
    JobDescription,
)

_KNOWN_ORIGIN_TYPES = frozenset({"copy_paste"}) | URL_ORIGIN_TYPES


def _require_jd(state: JdExtractState) -> JobDescription:
    jd = state.get("jd")
    if jd is None:
        raise ValueError("jd is required; run load_jd first")
    return jd


def load_jd(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Load the existing JD row and validate origin fields."""
    jd_id = str(state.get("jd_id") or "").strip()
    if not jd_id:
        raise ValueError("jd_id is required")

    client = client_from_env()
    row = jd_repo.get_by_id(client, jd_id)
    if row is None:
        raise ValueError(f"No job_description row for id={jd_id}")

    origin_jd = (row.origin_jd or "").strip()
    if not origin_jd:
        raise ValueError(f"origin_jd is empty for jd_id={jd_id}")

    origin_type = (row.origin_type or "").strip()
    if origin_type not in _KNOWN_ORIGIN_TYPES:
        raise ValueError(
            f"Unknown origin_type={origin_type!r} for jd_id={jd_id}. "
            f"Expected one of: {sorted(_KNOWN_ORIGIN_TYPES)}"
        )

    return {"jd": row}


def route_by_origin_type(
    state: JdExtractState,
) -> Literal["fetch_jd", "prepare_jd_text"]:
    """Route URL origins through fetch_jd; copy_paste goes to prepare_jd_text."""
    jd = _require_jd(state)
    if jd.origin_type in URL_ORIGIN_TYPES:
        return "fetch_jd"
    return "prepare_jd_text"


def mark_extracting(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Mark the JD as ``extracting`` and publish ``process.jd-extraction/started``."""
    jd_id = str(state["jd_id"])
    client = client_from_env()
    jd_repo.update_extraction_status(client, jd_id, "extracting")
    ProcessEventPublisher().publish(
        JdExtractionStarted(
            job_id=jd_id,
            job_description_id=jd_id,
            trace_id=_trace_id(config),
        )
    )
    return {"extraction_status": "extracting"}


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


def resolve_company(state: JdExtractState) -> dict[str, Any]:
    """Resolve ``jd.company_name`` to an existing ``company_id`` and persist both.

    Runs after skills are saved. Uses the mock company-resolution tool until
    the real company data layer is wired.
    """
    jd = _require_jd(state)
    company_name = (jd.company_name or "").strip()
    if not company_name:
        raise ValueError("company_name is required before resolve_company")
    company_id = str(resolve_company_id.invoke({"company_name": company_name})).strip()
    if not company_id:
        raise ValueError("resolve_company_id returned an empty company_id")

    client = client_from_env()
    updated = jd_repo.update_company(
        client,
        state["jd_id"],
        company_id=company_id,
        company_name=company_name,
    )
    return {
        "company_id": company_id,
        "jd": updated,
    }


def mark_done(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Mark the JD record as ``done`` and publish ``process.jd-extraction/finish``.

    The finish payload includes ``skills`` and ``sections`` so downstream
    consumers can persist the extraction result.
    """
    jd_id = state["jd_id"]
    client = client_from_env()
    jd_repo.update_extraction_status(client, jd_id, "done")
    row = jd_repo.get_by_id(client, jd_id)
    if row is None:
        raise ValueError(f"No job_description row for id={jd_id}")

    ProcessEventPublisher().publish(
        JdExtractionFinish(
            job_id=str(jd_id),
            job_description_id=str(jd_id),
            trace_id=_trace_id(config),
            payload=JdExtractionFinishPayload(
                skills=[skill.model_dump() for skill in row.skills],
                sections=dict(row.sections),
            ),
        )
    )
    return {"extraction_status": "done"}


def _trace_id(config: RunnableConfig) -> str | None:
    configurable = (config or {}).get("configurable") or {}
    raw = configurable.get("thread_id") or configurable.get("run_id")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None

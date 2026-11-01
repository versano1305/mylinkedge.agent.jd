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


@thinking("Loading job description…")
def load_jd(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Load the existing JD row and validate origin fields."""
    _ = config
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


@thinking("Starting JD extraction…")
def mark_extracting(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Mark the JD as ``extracting``."""
    _ = config
    jd_id = str(state["jd_id"])
    client = client_from_env()
    jd_repo.update_extraction_status(client, jd_id, "extracting")
    return {"extraction_status": "extracting"}


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


@thinking("Finishing JD extraction…")
def mark_done(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Mark the JD record as ``done`` and signal completion to stream clients."""
    _ = config
    jd_id = state["jd_id"]
    client = client_from_env()
    jd_repo.update_extraction_status(client, jd_id, "done")
    row = jd_repo.get_by_id(client, jd_id)
    if row is None:
        raise ValueError(f"No job_description row for id={jd_id}")

    emit_client_event(
        "jd_extraction_finish",
        {
            "job_description_id": str(jd_id),
            "skills": [skill.model_dump() for skill in row.skills],
            "sections": dict(row.sections),
        },
    )
    emit_finish_interview()
    return {"extraction_status": "done"}

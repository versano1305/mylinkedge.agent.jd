"""Validate the job description supplied on the initial graph state."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.langgraph_streaming.annotations import thinking

from jd_agent.graphs.jd_extract.state import JdExtractState
from jd_agent.integrations.supabase.jd_repository import URL_ORIGIN_TYPES, JobDescription
from jd_agent.shared.jd_event_hub import publish_jd_extraction_start_from_state

_KNOWN_ORIGIN_TYPES = frozenset({"copy_paste"}) | URL_ORIGIN_TYPES


def _job_description(state: JdExtractState) -> JobDescription:
    raw = state.get("jd")
    if raw is None:
        raise ValueError("jd is required")
    if isinstance(raw, JobDescription):
        return raw
    if isinstance(raw, dict):
        return JobDescription.model_validate(raw)
    raise ValueError("jd must be a job description")


@thinking("Validating job description…")
def initialize(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Validate the JD already present on the initial state.

    The row exists in the database before invoke. Callers pass that object
    as ``jd``; this node checks identity and origin fields, publishes
    ``jd_extraction_start``, and sets ``extraction_status`` to ``extracting``.
    """
    jd = _job_description(state)
    jd_id = str(jd.id or "").strip()
    if not jd_id:
        raise ValueError("jd.id is required")

    incoming_id = str(state.get("jd_id") or "").strip()
    if incoming_id and incoming_id != jd_id:
        raise ValueError(f"jd_id={incoming_id!r} does not match jd.id={jd_id!r}")

    origin_jd = (jd.origin_jd or "").strip()
    if not origin_jd:
        raise ValueError(f"origin_jd is empty for jd_id={jd_id}")

    origin_type = (jd.origin_type or "").strip()
    if origin_type not in _KNOWN_ORIGIN_TYPES:
        raise ValueError(
            f"Unknown origin_type={origin_type!r} for jd_id={jd_id}. "
            f"Expected one of: {sorted(_KNOWN_ORIGIN_TYPES)}"
        )

    publish_state = dict(state)
    publish_state["jd_id"] = jd_id
    publish_state["jd"] = jd
    publish_jd_extraction_start_from_state(publish_state, config)
    return {"jd": jd, "jd_id": jd_id, "extraction_status": "extracting"}

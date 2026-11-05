"""Session load, status markers, and persistence nodes.

Thin I/O nodes pending per-folder migration (mirrors ``jd_extract`` layout).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.langgraph_streaming.annotations import thinking
from mylinkedge_agent_tools.langgraph_streaming.custom_events import emit_finish_interview
from mylinkedge_agent_tools.postgres import get_postgres_db

from jd_agent.graphs.gap_collect.state import GapCollectState
from jd_agent.integrations.supabase.jd_repository import normalize_job_description
from jd_agent.integrations.supabase.user_resume_builder_repository import (
    normalize_user_resume_builder,
)
from jd_agent.shared.jd_event_hub import (
    publish_jd_gap_analysis_data_from_state,
    publish_jd_gap_analysis_end_from_state,
    publish_jd_gap_analysis_start_from_state,
)


@thinking("Loading resume-builder session…")
def load_session(
    state: GapCollectState, config: RunnableConfig
) -> dict[str, Any]:
    """Load the resume-builder session and its joined job description."""
    _ = config
    session_id = str(state.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required")

    loaded = get_postgres_db().user_resume_builders.get_with_job_description(session_id)
    if loaded is None:
        raise ValueError(f"No user_resume_builder row for id={session_id}")

    session = normalize_user_resume_builder(loaded.session.model_dump())
    jd = normalize_job_description(loaded.job_description.model_dump())

    if jd.extraction_status != "done":
        raise ValueError(
            f"job_description {jd.id} is not extracted "
            f"(extraction_status={jd.extraction_status!r}); run jd_extract first"
        )

    return {
        "session": session,
        "jd": jd,
        "user_id": session.user_id,
        "job_description_id": session.job_description_id,
    }


@thinking("Starting gap analysis…")
def mark_analyzing(
    state: GapCollectState, config: RunnableConfig
) -> dict[str, Any]:
    """Publish ``JD_GAP_ANALYSIS_START`` for downstream status updates."""
    publish_jd_gap_analysis_start_from_state(state, config)
    return {"gap_status": "analyzing"}


@thinking("Saving gap analysis…")
def save_gaps(state: GapCollectState, config: RunnableConfig) -> dict[str, Any]:
    """Publish gaps jsonb via ``JD_GAP_ANALYSIS_DATA`` for consumer persistence."""
    gaps = dict(state.get("gaps") or {})
    if not gaps:
        raise ValueError("gaps must be computed before save_gaps")

    gaps_date = datetime.now(UTC).isoformat()
    publish_jd_gap_analysis_data_from_state(
        state,
        kind="gaps",
        data={"gaps": gaps, "gaps_date": gaps_date},
        config=config,
    )
    return {}


@thinking("Finishing gap analysis…")
def mark_done(state: GapCollectState, config: RunnableConfig) -> dict[str, Any]:
    """Publish ``JD_GAP_ANALYSIS_END`` and signal completion to stream clients."""
    publish_jd_gap_analysis_end_from_state(state, config)
    emit_finish_interview()
    return {"gap_status": "done"}

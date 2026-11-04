"""Session load, status markers, and persistence nodes.

Thin I/O nodes pending per-folder migration (mirrors ``jd_extract`` layout).
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.langgraph_streaming.annotations import thinking
from mylinkedge_agent_tools.langgraph_streaming.custom_events import emit_finish_interview

from jd_agent.graphs.gap_collect.state import GapCollectState
from jd_agent.integrations.supabase import (
    user_resume_builder_repository as urb_repo,
)
from jd_agent.integrations.supabase.client import client_from_env
from jd_agent.shared.jd_event_hub import publish_jd_gap_analysis_start_from_state


@thinking("Loading resume-builder session…")
def load_session(
    state: GapCollectState, config: RunnableConfig
) -> dict[str, Any]:
    """Load the resume-builder session and its joined job description."""
    session_id = str(state.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required")

    client = client_from_env()
    loaded = urb_repo.get_session_with_jd(client, session_id)
    if loaded is None:
        raise ValueError(f"No user_resume_builder row for id={session_id}")

    updates = {
        "session": loaded.session,
        "jd": loaded.job_description,
        "user_id": loaded.session.user_id,
        "job_description_id": loaded.session.job_description_id,
    }
    publish_jd_gap_analysis_start_from_state({**state, **updates}, config)

    jd = loaded.job_description
    if jd.extraction_status != "done":
        raise ValueError(
            f"job_description {jd.id} is not extracted "
            f"(extraction_status={jd.extraction_status!r}); run jd_extract first"
        )

    return updates


@thinking("Starting gap analysis…")
def mark_analyzing(
    state: GapCollectState, config: RunnableConfig
) -> dict[str, Any]:
    """Mark gap analysis in progress on the session."""
    _ = config
    session_id = str(state.get("session_id") or "").strip()
    client = client_from_env()
    urb_repo.mark_gap_analysis_in_progress(client, session_id)
    return {"gap_status": "analyzing"}


@thinking("Saving gap analysis…")
def save_gaps(state: GapCollectState, config: RunnableConfig) -> dict[str, Any]:
    """Persist the gaps jsonb and advance the session to the gap-interview step."""
    _ = config
    session_id = str(state.get("session_id") or "").strip()
    gaps = dict(state.get("gaps") or {})
    if not gaps:
        raise ValueError("gaps must be computed before save_gaps")

    client = client_from_env()
    updated = urb_repo.save_gaps(client, session_id, gaps)
    return {"session": updated}


@thinking("Finishing gap analysis…")
def mark_done(state: GapCollectState, config: RunnableConfig) -> dict[str, Any]:
    """Signal completion to stream clients after gaps are persisted."""
    _ = config
    emit_finish_interview()
    return {"gap_status": "done"}

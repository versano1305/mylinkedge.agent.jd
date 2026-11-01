"""Mark the generate step in progress on the session."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.postgres import (
    get_postgres_db,
    in_progress_user_resume_builder_status,
)

from jd_agent.graphs.resume_generate.state import ResumeGenerateState

GENERATE_STEP = "template"


def mark_generating(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Set status to ``template_in_progress`` on the resume-builder session."""

    _ = config
    session_id = str(state.get("session_id") or "").strip()
    updated = get_postgres_db().user_resume_builders.update_status(
        session_id, in_progress_user_resume_builder_status(GENERATE_STEP)
    )
    return {"session": updated}


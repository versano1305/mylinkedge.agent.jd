"""WU-12 — Assemble JSON Resume + trace and persist on the session."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.postgres import get_postgres_db

from jd_agent.graphs.resume_generate.nodes.assemble_and_save.resume_document import (
    build_resume_document,
)
from jd_agent.graphs.resume_generate.nodes.assemble_and_save.trace_document import (
    build_trace_document,
)
from jd_agent.graphs.resume_generate.state import ResumeGenerateState


def _skip_persist() -> bool:
    return os.getenv("RESUME_GENERATE_SKIP_PERSIST", "").strip() == "1"


def assemble_and_save(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Build resume + trace, persist when allowed, and mark the run complete."""

    _ = config
    resume = build_resume_document(state)
    trace = build_trace_document(state).model_dump()

    session_id = str(state.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required for assemble_and_save")

    session = state.get("session")
    if not _skip_persist():
        session = get_postgres_db().user_resume_builders.save_resume(
            session_id, resume, trace
        )

    return {
        "resume": resume,
        "trace": trace,
        "session": session,
        "generate_status": "done",
    }

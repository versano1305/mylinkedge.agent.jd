"""WU-12 — Assemble JSON Resume + trace and publish for consumer persistence."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.nodes.assemble_and_save.resume_document import (
    build_resume_document,
)
from jd_agent.graphs.resume_generate.nodes.assemble_and_save.trace_document import (
    build_trace_document,
)
from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.shared.jd_event_hub import publish_resume_generate_data_from_state



def assemble_and_save(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Build resume + trace, publish ``RESUME_GENERATE_DATA`` when allowed."""

    resume = build_resume_document(state)
    trace = build_trace_document(state).model_dump()

    session_id = str(state.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required for assemble_and_save")

    resume_date = datetime.now(UTC).isoformat()
    publish_resume_generate_data_from_state(
        state,
        kind="resume",
        data={
            "resume": resume,
            "resume_trace": trace,
            "resume_date": resume_date,
        },
        config=config,
    )

    return {
        "resume": resume,
        "trace": trace,
        "session": state.get("session"),
        "generate_status": "done",
    }

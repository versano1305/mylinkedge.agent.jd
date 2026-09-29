"""Mark the generate step in progress on the session."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.event_hub import ProcessEventPublisher, ResumeGenerateStarted
from mylinkedge_agent_tools.postgres import (
    get_postgres_db,
    in_progress_user_resume_builder_status,
)

from jd_agent.graphs.resume_generate.state import ResumeGenerateState

GENERATE_STEP = "template"


def mark_generating(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Set status to ``template_in_progress`` and publish ``process.resume-generate/started``.

    The library started payload is empty. ``job_id`` is the job-description id
    on the updated session. A transport failure is recorded on ``errors``.
    """

    session_id = str(state.get("session_id") or "").strip()
    updated = get_postgres_db().user_resume_builders.update_status(
        session_id, in_progress_user_resume_builder_status(GENERATE_STEP)
    )
    errors = list(state.get("errors") or [])
    try:
        ProcessEventPublisher().publish(
            ResumeGenerateStarted(
                job_id=str(updated.job_description_id or ""),
                trace_id=_trace_id(config),
            )
        )
    except Exception as exc:  # noqa: BLE001 - event transport is best-effort here
        errors.append(f"resume-generate started publish failed: {type(exc).__name__}")
    return {"session": updated, "errors": errors}


def _trace_id(config: RunnableConfig) -> str | None:
    configurable = (config or {}).get("configurable") or {}
    raw = configurable.get("thread_id") or configurable.get("run_id")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None

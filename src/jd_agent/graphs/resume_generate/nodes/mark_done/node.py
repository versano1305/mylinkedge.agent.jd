"""Publish resume-generate finish event (best-effort)."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.event_hub import ProcessEventPublisher, ResumeGenerateFinish
from mylinkedge_agent_tools.postgres import UserResumeBuilder

from jd_agent.graphs.resume_generate.state import ResumeGenerateState


def mark_done(state: ResumeGenerateState, config: RunnableConfig) -> dict[str, Any]:
    """Publish ``process.resume-generate/finish`` after persistence.

    The library finish payload is empty. ``job_id`` is the job-description id
    on the session. A transport failure is recorded on ``errors``.
    """

    return _publish(
        state,
        ResumeGenerateFinish(
            job_id=_job_id(state),
            trace_id=_trace_id(config),
        ),
        error_label="resume-generate finish",
    )


def _publish(
    state: ResumeGenerateState,
    event: ResumeGenerateFinish,
    *,
    error_label: str,
) -> dict[str, Any]:
    errors = list(state.get("errors") or [])
    try:
        ProcessEventPublisher().publish(event)
    except Exception as exc:  # noqa: BLE001 - event transport is best-effort here
        errors.append(f"{error_label} publish failed: {type(exc).__name__}")
    return {"errors": errors}


def _job_id(state: ResumeGenerateState) -> str:
    session = state.get("session")
    if isinstance(session, UserResumeBuilder):
        return str(session.job_description_id or "")
    return ""


def _trace_id(config: RunnableConfig) -> str | None:
    configurable = (config or {}).get("configurable") or {}
    raw = configurable.get("thread_id") or configurable.get("run_id")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None

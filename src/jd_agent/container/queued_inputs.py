"""Map queued process events onto graph invoke inputs."""

from __future__ import annotations

from typing import Any

from mylinkedge_agent_tools.event_hub import (
    HandlerPermanentError,
    JdExtractionQueued,
    JdGapAnalysisQueued,
    ResumeGenerateQueued,
)

JD_EXTRACT_GRAPH = "jd_extract"
GAP_COLLECT_GRAPH = "gap_collect"
RESUME_GENERATE_GRAPH = "resume_generate"


def jd_extraction_input(event: JdExtractionQueued) -> dict[str, Any]:
    """``jd_extract`` is invoked with the existing job-description id."""

    jd_id = event.job_description_id.strip()
    if not jd_id:
        raise HandlerPermanentError("job_description_id is required")
    return {"jd_id": jd_id}


def gap_analysis_input(event: JdGapAnalysisQueued) -> dict[str, Any]:
    """``gap_collect`` is invoked with the resume-builder session id."""

    return {"session_id": _required_session_id(event.payload.session_id)}


def resume_generate_input(event: ResumeGenerateQueued) -> dict[str, Any]:
    """``resume_generate`` is invoked with the resume-builder session id."""

    return {"session_id": _required_session_id(event.payload.session_id)}


def thread_id_for(
    event: JdExtractionQueued | JdGapAnalysisQueued | ResumeGenerateQueued,
) -> str | None:
    """LangGraph thread id from the event, when the publisher set one."""

    raw = event.run_id or event.trace_id
    if raw is None:
        return None
    thread_id = str(raw).strip()
    return thread_id or None


def _required_session_id(session_id: str) -> str:
    cleaned = session_id.strip()
    if not cleaned:
        raise HandlerPermanentError("session_id is required")
    return cleaned

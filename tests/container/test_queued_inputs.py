"""Queued process events map onto graph invoke inputs."""

from __future__ import annotations

import pytest
from mylinkedge_agent_tools.event_hub import (
    HandlerPermanentError,
    JdExtractionQueued,
    JdGapAnalysisQueued,
    JdGapAnalysisQueuedPayload,
    ResumeGenerateQueued,
    ResumeGenerateQueuedPayload,
)

from jd_agent.container.queued_inputs import (
    gap_analysis_input,
    jd_extraction_input,
    resume_generate_input,
    thread_id_for,
)


def test_jd_extraction_uses_job_description_id() -> None:
    event = JdExtractionQueued(job_id="job-1", job_description_id="jd-1", trace_id="run-1")

    assert jd_extraction_input(event) == {"jd_id": "jd-1"}
    assert thread_id_for(event) == "run-1"


def test_jd_extraction_rejects_blank_id() -> None:
    event = JdExtractionQueued(job_id="job-1", job_description_id="  ")

    with pytest.raises(HandlerPermanentError, match="job_description_id"):
        jd_extraction_input(event)


def test_gap_analysis_uses_session_id() -> None:
    event = JdGapAnalysisQueued(
        job_id="job-1",
        job_description_id="jd-1",
        payload=JdGapAnalysisQueuedPayload(session_id="session-1"),
    )

    assert gap_analysis_input(event) == {"session_id": "session-1"}


def test_gap_analysis_rejects_blank_session_id() -> None:
    event = JdGapAnalysisQueued(
        job_id="job-1",
        job_description_id="jd-1",
        payload=JdGapAnalysisQueuedPayload(session_id="  "),
    )

    with pytest.raises(HandlerPermanentError, match="session_id"):
        gap_analysis_input(event)


def test_resume_generate_uses_session_id() -> None:
    event = ResumeGenerateQueued(
        job_id="job-1",
        run_id="run-9",
        payload=ResumeGenerateQueuedPayload(session_id="session-9"),
    )

    assert resume_generate_input(event) == {"session_id": "session-9"}
    assert thread_id_for(event) == "run-9"


def test_resume_generate_rejects_blank_session_id() -> None:
    event = ResumeGenerateQueued(
        job_id="job-1",
        payload=ResumeGenerateQueuedPayload(session_id=""),
    )

    with pytest.raises(HandlerPermanentError, match="session_id"):
        resume_generate_input(event)

"""SQS handlers dispatch queued events to the graph invoker."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from mylinkedge_agent_tools.event_hub import (
    EventMessageContext,
    GraphId,
    HandlerPermanentError,
    HandlerRetryError,
    JdExtractionQueued,
    JdGapAnalysisQueued,
    ResumeGenerateQueued,
)
from mylinkedge_agent_tools.event_hub.lifecycle import (
    JdExtractionQueuedPayload,
    JdGapAnalysisQueuedPayload,
    ResumeGenerateQueuedPayload,
)

from jd_agent.container.runners.sqs.worker import (
    DEFAULT_QUEUE_NAME,
    AgentJdProcessConsumer,
)


def _ctx() -> EventMessageContext:
    return EventMessageContext(
        message_id="msg-1",
        receipt_handle="receipt-1",
        raw_body="{}",
    )


def _consumer(invoker: AsyncMock) -> AgentJdProcessConsumer:
    return AgentJdProcessConsumer(consumer=MagicMock(), invoker=invoker)


def test_registers_the_three_queued_types() -> None:
    worker = _consumer(AsyncMock())

    assert set(worker._dispatcher.registered_types()) == {
        "jd_extraction_queued",
        "jd_gap_analysis_queued",
        "resume_generate_queued",
    }


def test_queue_name_defaults_and_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    worker = _consumer(AsyncMock())
    monkeypatch.delenv("SQS_QUEUE_NAME", raising=False)
    assert worker._queue_name() == DEFAULT_QUEUE_NAME

    monkeypatch.setenv("SQS_QUEUE_NAME", "custom-agent-jd-events")
    assert worker._queue_name() == "custom-agent-jd-events"


def test_resume_generate_invokes_graph() -> None:
    invoker = AsyncMock()
    invoker.invoke.return_value = {"generate_status": "done"}
    worker = _consumer(invoker)
    event = ResumeGenerateQueued(
        initiator=GraphId.RESUME_GENERATE,
        payload=ResumeGenerateQueuedPayload(
            job_id="job-1",
            session_id="session-1",
            run_id="trace-1",
        ),
    )

    asyncio.run(worker.handle_resume_generate(event, _ctx()))

    invoker.invoke.assert_awaited_once_with(
        "resume_generate",
        {"session_id": "session-1"},
        thread_id="trace-1",
    )


def test_dispatch_raw_body_to_jd_extraction() -> None:
    invoker = AsyncMock()
    invoker.invoke.return_value = {"extraction_status": "done"}
    worker = _consumer(invoker)
    event = JdExtractionQueued(
        initiator=GraphId.JD_EXTRACT,
        payload=JdExtractionQueuedPayload(
            job_id="jd-1",
            job_description_id="jd-1",
            run_id="run-1",
        ),
    )

    asyncio.run(worker._handle_raw(event.model_dump_json(), _ctx()))

    invoker.invoke.assert_awaited_once_with(
        "jd_extract",
        {"jd_id": "jd-1"},
        thread_id="run-1",
    )


def test_gap_analysis_blank_session_is_permanent() -> None:
    invoker = AsyncMock()
    worker = _consumer(invoker)
    event = JdGapAnalysisQueued(
        initiator=GraphId.GAP_COLLECT,
        payload=JdGapAnalysisQueuedPayload(
            job_id="job-1",
            job_description_id="jd-1",
            session_id="  ",
        ),
    )

    with pytest.raises(HandlerPermanentError):
        asyncio.run(worker.handle_gap_analysis(event, _ctx()))
    invoker.invoke.assert_not_awaited()


def test_graph_failure_is_retried() -> None:
    invoker = AsyncMock()
    invoker.invoke.side_effect = RuntimeError("database down")
    worker = _consumer(invoker)
    event = ResumeGenerateQueued(
        initiator=GraphId.RESUME_GENERATE,
        payload=ResumeGenerateQueuedPayload(job_id="job-1", session_id="session-1"),
    )

    with pytest.raises(HandlerRetryError, match="database down"):
        asyncio.run(worker.handle_resume_generate(event, _ctx()))

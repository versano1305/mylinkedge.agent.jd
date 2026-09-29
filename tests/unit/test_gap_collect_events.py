"""Unit tests for gap-collect start and finish events."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from jd_agent.graphs.gap_collect.nodes._legacy import mark_analyzing, mark_done


def test_mark_analyzing_publishes_started_event() -> None:
    mock_publisher = MagicMock()
    with (
        patch(
            "jd_agent.graphs.gap_collect.nodes._legacy.client_from_env",
            return_value=MagicMock(),
        ),
        patch(
            "jd_agent.graphs.gap_collect.nodes._legacy.urb_repo.mark_gap_analysis_in_progress",
        ) as mock_status,
        patch(
            "jd_agent.graphs.gap_collect.nodes._legacy.ProcessEventPublisher",
            return_value=mock_publisher,
        ),
    ):
        result = mark_analyzing(
            {"session_id": "sess-1", "job_description_id": "jd-9"},
            {"configurable": {"thread_id": "thread-4"}},
        )

    mock_status.assert_called_once()
    assert result["gap_status"] == "analyzing"
    assert result["errors"] == []
    event = mock_publisher.publish.call_args.args[0]
    assert event.type == "process.jd-gap-analysis/started"
    assert event.job_id == "jd-9"
    assert event.job_description_id == "jd-9"
    assert event.trace_id == "thread-4"
    assert event.payload.model_dump() == {}


def test_mark_done_publishes_finish_event() -> None:
    mock_publisher = MagicMock()
    with patch(
        "jd_agent.graphs.gap_collect.nodes._legacy.ProcessEventPublisher",
        return_value=mock_publisher,
    ):
        result = mark_done(
            {"job_description_id": "jd-9"},
            {"configurable": {"run_id": "run-2"}},
        )

    assert result == {"gap_status": "done", "errors": []}
    event = mock_publisher.publish.call_args.args[0]
    assert event.type == "process.jd-gap-analysis/finish"
    assert event.job_id == "jd-9"
    assert event.job_description_id == "jd-9"
    assert event.trace_id == "run-2"
    assert event.payload.model_dump() == {}

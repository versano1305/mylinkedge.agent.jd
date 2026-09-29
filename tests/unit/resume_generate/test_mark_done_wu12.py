"""Unit tests for resume-generate start and finish events."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from mylinkedge_agent_tools.postgres import UserResumeBuilder

from jd_agent.graphs.resume_generate.nodes.mark_done.node import mark_done


def test_mark_done_publishes_finish_event() -> None:
    mock_publisher = MagicMock()
    session = UserResumeBuilder(
        id="sess-1",
        user_id="user-1",
        status="generate_in_progress",
        job_description_id="jd-1",
    )
    with patch(
        "jd_agent.graphs.resume_generate.nodes.mark_done.node.ProcessEventPublisher",
        return_value=mock_publisher,
    ):
        result = mark_done(
            {"session_id": "sess-1", "session": session},
            {"configurable": {"thread_id": "thread-9"}},
        )

    assert result == {"errors": []}
    mock_publisher.publish.assert_called_once()
    event = mock_publisher.publish.call_args.args[0]
    assert event.type == "process.resume-generate/finish"
    assert event.job_id == "jd-1"
    assert event.trace_id == "thread-9"
    assert event.payload.model_dump() == {}

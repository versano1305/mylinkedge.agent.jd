"""Unit tests for gap-collect status marker nodes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from jd_agent.graphs.gap_collect.nodes._legacy import mark_analyzing, mark_done, save_gaps


def test_mark_analyzing_publishes_start() -> None:
    with patch(
        "jd_agent.graphs.gap_collect.nodes._legacy.publish_jd_gap_analysis_start_from_state",
    ) as mock_start:
        result = mark_analyzing(
            {
                "session_id": "sess-1",
                "job_description_id": "jd-9",
                "user_id": "user-1",
            },
            {"configurable": {"thread_id": "thread-4"}},
        )

    mock_start.assert_called_once()
    assert result == {"gap_status": "analyzing"}


def test_save_gaps_publishes_data() -> None:
    gaps = {"schema_version": 1, "meta": {}, "review": {}, "skills": {}, "interview": {}}
    with patch(
        "jd_agent.graphs.gap_collect.nodes._legacy.publish_jd_gap_analysis_data_from_state",
    ) as mock_data:
        result = save_gaps(
            {
                "session_id": "sess-1",
                "job_description_id": "jd-9",
                "gaps": gaps,
            },
            {"configurable": {"run_id": "run-1"}},
        )

    mock_data.assert_called_once()
    call = mock_data.call_args
    assert call.kwargs["kind"] == "gaps"
    assert call.kwargs["data"]["gaps"] == gaps
    assert isinstance(call.kwargs["data"]["gaps_date"], str)
    assert result == {}


def test_mark_done_publishes_end_and_streams_finish() -> None:
    with (
        patch(
            "jd_agent.graphs.gap_collect.nodes._legacy.publish_jd_gap_analysis_end_from_state",
        ) as mock_end,
        patch(
            "jd_agent.graphs.gap_collect.nodes._legacy.emit_finish_interview",
        ) as mock_finish,
    ):
        result = mark_done(
            {
                "session_id": "sess-1",
                "job_description_id": "jd-9",
            },
            {"configurable": {"run_id": "run-2"}},
        )

    mock_end.assert_called_once()
    mock_finish.assert_called_once()
    assert result == {"gap_status": "done"}

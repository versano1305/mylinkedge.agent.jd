"""Unit tests for gap-collect status marker nodes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from jd_agent.graphs.gap_collect.nodes._legacy import mark_analyzing, mark_done


def test_mark_analyzing_updates_session_status() -> None:
    with (
        patch(
            "jd_agent.graphs.gap_collect.nodes._legacy.client_from_env",
            return_value=MagicMock(),
        ),
        patch(
            "jd_agent.graphs.gap_collect.nodes._legacy.urb_repo.mark_gap_analysis_in_progress",
        ) as mock_status,
    ):
        result = mark_analyzing(
            {"session_id": "sess-1", "job_description_id": "jd-9"},
            {"configurable": {"thread_id": "thread-4"}},
        )

    mock_status.assert_called_once()
    assert result == {"gap_status": "analyzing"}


def test_mark_done_streams_finish() -> None:
    with patch(
        "jd_agent.graphs.gap_collect.nodes._legacy.emit_finish_interview",
    ) as mock_finish:
        result = mark_done(
            {"job_description_id": "jd-9"},
            {"configurable": {"run_id": "run-2"}},
        )

    assert result == {"gap_status": "done"}
    mock_finish.assert_called_once()

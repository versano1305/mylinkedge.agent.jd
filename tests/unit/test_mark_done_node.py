"""Unit tests for mark_done node."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from jd_agent.graphs.jd_extract.nodes import mark_done, mark_extracting
from jd_agent.integrations.supabase.jd_repository import (
    JobDescription,
    JobDescriptionSkill,
)


def test_mark_done_updates_status_and_streams_finish() -> None:
    row = JobDescription(
        id="jd-42",
        skills=[JobDescriptionSkill(name="Python", source="taxonomy")],
        sections={"requirements": "3+ years Python"},
        extraction_status="done",
    )
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.client_from_env",
            return_value=MagicMock(),
        ) as mock_client_from_env,
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.jd_repo.update_extraction_status",
        ) as mock_update,
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.jd_repo.get_by_id",
            return_value=row,
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.emit_client_event",
        ) as mock_client_event,
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.emit_finish_interview",
        ) as mock_finish,
    ):
        result = mark_done(
            {"jd_id": "jd-42"},
            {"configurable": {"thread_id": "thread-7"}},
        )

    assert result == {"extraction_status": "done"}
    mock_update.assert_called_once_with(
        mock_client_from_env.return_value,
        "jd-42",
        "done",
    )
    mock_client_event.assert_called_once()
    kind, payload = mock_client_event.call_args.args
    assert kind == "jd_extraction_finish"
    assert payload["job_description_id"] == "jd-42"
    assert payload["skills"] == [
        {
            "id": None,
            "name": "Python",
            "requirement_level": 1.0,
            "source": "taxonomy",
        }
    ]
    assert payload["sections"] == {"requirements": "3+ years Python"}
    mock_finish.assert_called_once()


def test_mark_extracting_updates_status() -> None:
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.client_from_env",
            return_value=MagicMock(),
        ) as mock_client_from_env,
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.jd_repo.update_extraction_status",
        ) as mock_update,
    ):
        result = mark_extracting(
            {"jd_id": "jd-42"},
            {"configurable": {"thread_id": "thread-7"}},
        )

    assert result == {"extraction_status": "extracting"}
    mock_update.assert_called_once_with(
        mock_client_from_env.return_value,
        "jd-42",
        "extracting",
    )

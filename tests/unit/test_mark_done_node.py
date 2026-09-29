"""Unit tests for mark_done node."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from jd_agent.graphs.jd_extract.nodes import mark_done, mark_extracting
from jd_agent.integrations.supabase.jd_repository import (
    JobDescription,
    JobDescriptionSkill,
)


def test_mark_done_updates_status_and_publishes_finish_event() -> None:
    row = JobDescription(
        id="jd-42",
        skills=[JobDescriptionSkill(name="Python", source="taxonomy")],
        sections={"requirements": "3+ years Python"},
        extraction_status="done",
    )
    mock_publisher = MagicMock()
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
            "jd_agent.graphs.jd_extract.nodes._legacy.ProcessEventPublisher",
            return_value=mock_publisher,
        ),
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
    mock_publisher.publish.assert_called_once()
    event = mock_publisher.publish.call_args.args[0]
    assert event.type == "process.jd-extraction/finish"
    assert event.job_id == "jd-42"
    assert event.job_description_id == "jd-42"
    assert event.trace_id == "thread-7"
    assert event.payload.skills == [
        {
            "id": None,
            "name": "Python",
            "requirement_level": 1.0,
            "source": "taxonomy",
        }
    ]
    assert event.payload.sections == {"requirements": "3+ years Python"}


def test_mark_extracting_publishes_started_event() -> None:
    mock_publisher = MagicMock()
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.client_from_env",
            return_value=MagicMock(),
        ) as mock_client_from_env,
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.jd_repo.update_extraction_status",
        ) as mock_update,
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.ProcessEventPublisher",
            return_value=mock_publisher,
        ),
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
    mock_publisher.publish.assert_called_once()
    event = mock_publisher.publish.call_args.args[0]
    assert event.type == "process.jd-extraction/started"
    assert event.job_id == "jd-42"
    assert event.job_description_id == "jd-42"
    assert event.trace_id == "thread-7"
    assert event.payload.section is None

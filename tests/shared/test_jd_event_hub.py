"""Tests for JD-agent lifecycle event-hub publishing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from jd_agent.shared import jd_event_hub as hub
from mylinkedge_agent_tools.event_hub.contract import GraphId, LifecycleType


@pytest.fixture(autouse=True)
def _enable_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JD_LIFECYCLE_EVENTS_ENABLED", "true")


@patch.object(hub, "HubPublisher")
def test_publish_jd_extraction_start(mock_hub_cls: MagicMock) -> None:
    publisher = MagicMock()
    mock_hub_cls.return_value = publisher

    hub.publish_jd_extraction_start(
        job_description_id="jd-1",
        job_id="job-1",
        user_id="user-1",
        run_id="run-1",
    )

    event = publisher.publish.call_args.args[0]
    assert event.type == LifecycleType.JD_EXTRACTION_START
    assert event.initiator == GraphId.JD_EXTRACT
    assert event.user_id == "user-1"
    assert event.payload.job_id == "job-1"
    assert event.payload.job_description_id == "jd-1"
    assert event.payload.run_id == "run-1"


@patch.object(hub, "HubPublisher")
def test_publish_jd_gap_analysis_start(mock_hub_cls: MagicMock) -> None:
    publisher = MagicMock()
    mock_hub_cls.return_value = publisher

    hub.publish_jd_gap_analysis_start(
        job_description_id="jd-9",
        job_id="session-1",
        user_id="user-9",
    )

    event = publisher.publish.call_args.args[0]
    assert event.type == LifecycleType.JD_GAP_ANALYSIS_START
    assert event.initiator == GraphId.GAP_COLLECT
    assert event.payload.job_description_id == "jd-9"
    assert event.payload.job_id == "session-1"
    assert event.user_id == "user-9"


@patch.object(hub, "HubPublisher")
def test_publish_resume_generate_start(mock_hub_cls: MagicMock) -> None:
    publisher = MagicMock()
    mock_hub_cls.return_value = publisher

    hub.publish_resume_generate_start(job_id="session-3", user_id="user-3", run_id="run-3")

    event = publisher.publish.call_args.args[0]
    assert event.type == LifecycleType.RESUME_GENERATE_START
    assert event.initiator == GraphId.RESUME_GENERATE
    assert event.payload.job_id == "session-3"
    assert event.payload.run_id == "run-3"
    assert event.user_id == "user-3"


@patch.object(hub, "publish_jd_extraction_start")
def test_publish_jd_extraction_start_from_state(mock_publish: MagicMock) -> None:
    hub.publish_jd_extraction_start_from_state(
        {"jd_id": "jd-2"},
        {"configurable": {"run_id": "run-2"}},
    )
    mock_publish.assert_called_once_with(
        job_description_id="jd-2",
        job_id="jd-2",
        user_id=None,
        run_id="run-2",
    )


@patch.object(hub, "publish_jd_gap_analysis_start")
def test_publish_jd_gap_analysis_start_from_state(mock_publish: MagicMock) -> None:
    hub.publish_jd_gap_analysis_start_from_state(
        {
            "session_id": "sess-1",
            "job_description_id": "jd-4",
            "user_id": "user-4",
        },
        {"configurable": {"thread_id": "thread-4"}},
    )
    mock_publish.assert_called_once_with(
        job_description_id="jd-4",
        job_id="sess-1",
        user_id="user-4",
        run_id="thread-4",
    )


@patch.object(hub, "publish_resume_generate_start")
def test_publish_resume_generate_start_from_state(mock_publish: MagicMock) -> None:
    hub.publish_resume_generate_start_from_state(
        {"session_id": "sess-9", "user_id": "user-9"},
        {},
    )
    mock_publish.assert_called_once_with(
        job_id="sess-9",
        user_id="user-9",
        run_id=None,
    )


def test_lifecycle_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JD_LIFECYCLE_EVENTS_ENABLED", "0")
    with patch.object(hub, "HubPublisher") as mock_hub_cls:
        hub.publish_jd_extraction_start(job_description_id="jd-1")
        mock_hub_cls.assert_not_called()

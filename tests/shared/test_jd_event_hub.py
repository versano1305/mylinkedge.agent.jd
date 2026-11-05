"""Tests for JD-agent lifecycle event-hub publishing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from mylinkedge_agent_tools.event_hub.contract import (
    ExpandType,
    GraphId,
    LifecycleType,
    LookupType,
)

from jd_agent.integrations.supabase.jd_repository import (
    JobDescription,
    JobDescriptionSkill,
)
from jd_agent.shared import jd_event_hub as hub


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
def test_publish_jd_extraction_end(mock_hub_cls: MagicMock) -> None:
    publisher = MagicMock()
    mock_hub_cls.return_value = publisher

    hub.publish_jd_extraction_end(
        job_description_id="jd-1",
        skills=[{"name": "Python"}],
        sections={"requirements": "Python"},
        job_id="job-1",
        user_id="user-1",
        run_id="run-1",
    )

    event = publisher.publish.call_args.args[0]
    assert event.type == LifecycleType.JD_EXTRACTION_END
    assert event.initiator == GraphId.JD_EXTRACT
    assert event.user_id == "user-1"
    assert event.payload.job_id == "job-1"
    assert event.payload.job_description_id == "jd-1"
    assert event.payload.run_id == "run-1"
    assert event.payload.skills == [{"name": "Python"}]
    assert event.payload.sections == {"requirements": "Python"}


@patch.object(hub, "publish_jd_extraction_end")
def test_publish_jd_extraction_end_from_state(mock_publish: MagicMock) -> None:
    hub.publish_jd_extraction_end_from_state(
        {"jd_id": "jd-2", "user_id": "user-2"},
        skills=[],
        sections={},
        config={"configurable": {"run_id": "run-2"}},
    )
    mock_publish.assert_called_once_with(
        job_description_id="jd-2",
        skills=[],
        sections={},
        job_id="jd-2",
        user_id="user-2",
        run_id="run-2",
    )


@patch.object(hub, "HubPublisher")
def test_publish_jd_extraction_data(mock_hub_cls: MagicMock) -> None:
    publisher = MagicMock()
    mock_hub_cls.return_value = publisher

    hub.publish_jd_extraction_data(
        job_description_id="jd-1",
        kind="sections",
        data={"sections": {"title": "Engineer"}, "title_name": "Engineer"},
        job_id="job-1",
        user_id="user-1",
        run_id="run-1",
    )

    event = publisher.publish.call_args.args[0]
    assert event.type == LifecycleType.JD_EXTRACTION_DATA
    assert event.initiator == GraphId.JD_EXTRACT
    assert event.user_id == "user-1"
    assert event.payload.job_id == "job-1"
    assert event.payload.job_description_id == "jd-1"
    assert event.payload.run_id == "run-1"
    assert event.payload.kind == "sections"
    assert event.payload.data == {
        "sections": {"title": "Engineer"},
        "title_name": "Engineer",
    }


@patch.object(hub, "publish_jd_extraction_data")
def test_publish_jd_extraction_data_from_state(mock_publish: MagicMock) -> None:
    hub.publish_jd_extraction_data_from_state(
        {"jd_id": "jd-2", "user_id": "user-2"},
        kind="sections",
        data={"sections": {}},
        config={"configurable": {"run_id": "run-2"}},
    )
    mock_publish.assert_called_once_with(
        job_description_id="jd-2",
        kind="sections",
        data={"sections": {}},
        job_id="jd-2",
        user_id="user-2",
        run_id="run-2",
    )


@patch.object(hub, "HubPublisher")
def test_publish_company_lookup(mock_hub_cls: MagicMock) -> None:
    publisher = MagicMock()
    mock_hub_cls.return_value = publisher

    hub.publish_company_lookup(
        company_name="Acme",
        job_description_id="jd-1",
        job_id="job-1",
        user_id="user-1",
        run_id="run-1",
    )

    event = publisher.publish.call_args.args[0]
    assert event.type == LookupType.COMPANY_LOOKUP
    assert event.initiator == GraphId.JD_EXTRACT
    assert event.user_id == "user-1"
    assert event.payload.nodes[0].label == "Company"
    assert event.payload.nodes[0].name == "Acme"
    assert event.payload.context == {
        "job_description_id": "jd-1",
        "job_id": "job-1",
        "run_id": "run-1",
    }


@patch.object(hub, "publish_company_lookup")
def test_publish_company_lookup_from_state(mock_publish: MagicMock) -> None:
    hub.publish_company_lookup_from_state(
        {"jd_id": "jd-2", "user_id": "user-2"},
        company_name="Acme",
        config={"configurable": {"run_id": "run-2"}},
    )
    mock_publish.assert_called_once_with(
        company_name="Acme",
        job_description_id="jd-2",
        job_id="jd-2",
        user_id="user-2",
        run_id="run-2",
    )


@patch.object(hub, "HubPublisher")
def test_publish_skill_linked(mock_hub_cls: MagicMock) -> None:
    publisher = MagicMock()
    mock_hub_cls.return_value = publisher

    hub.publish_skill_linked(
        links=[
            {
                "from_id": "jd-1",
                "relationship": "REQUIRES_SKILL",
                "to_id": "skill-1",
                "properties": {"name": "Python"},
            }
        ],
        context={"job_description_id": "jd-1", "skills": [{"id": "skill-1"}]},
        user_id="user-1",
    )

    event = publisher.publish.call_args.args[0]
    assert event.type == ExpandType.SKILL_LINKED
    assert event.initiator == GraphId.JD_EXTRACT
    assert event.user_id == "user-1"
    assert event.payload.links[0].from_id == "jd-1"
    assert event.payload.links[0].relationship == "REQUIRES_SKILL"
    assert event.payload.links[0].to_id == "skill-1"
    assert event.payload.links[0].properties == {"name": "Python"}
    assert event.payload.context["job_description_id"] == "jd-1"


@patch.object(hub, "publish_skill_linked")
def test_publish_skill_linked_from_state(mock_publish: MagicMock) -> None:
    hub.publish_skill_linked_from_state(
        {"jd_id": "jd-2", "user_id": "user-2"},
        links=[],
        context={"skills": []},
        config={"configurable": {"run_id": "run-2"}},
    )
    mock_publish.assert_called_once_with(
        links=[],
        context={
            "job_description_id": "jd-2",
            "job_id": "jd-2",
            "run_id": "run-2",
            "skills": [],
        },
        user_id="user-2",
    )


_EXTRACTED_SOLUTION_ARCHITECTURE = {
    "id": "69125e90-2545-4062-91e5-0e8de49185f6",
    "name": "Solution Architecture",
    "type": "Skill",
    "aliases": [
        "Enterprise Architecture",
        "Solution Design",
        "technical solution design",
        "Design Decision Authority",
        "Technical Architecture Selection",
        "Architecture Decision Making",
    ],
    "min_years": None,
    "importance": 1,
    "properties": {},
    "skill_type": "unknown",
    "is_existing": True,
    "surface_form": "Solutions Architect",
    "candidate_ids": [
        "69125e90-2545-4062-91e5-0e8de49185f6",
        "558d6a93-069f-4111-8537-7e9c4a042774",
    ],
    "substitutable": False,
    "evidence_sentence": "Amarel is hiring a Solutions Architect!",
}


@patch.object(hub, "publish_skill_linked")
def test_publish_skill_linked_from_state_includes_saved_skill_fields(
    mock_publish: MagicMock,
) -> None:
    hub.publish_skill_linked_from_state(
        {"jd_id": "jd-3", "user_id": "user-3"},
        links=[
            {
                "from_id": "jd-3",
                "relationship": "REQUIRES_SKILL",
                "to_id": "69125e90-2545-4062-91e5-0e8de49185f6",
                "properties": {"name": "Solution Architecture"},
            }
        ],
        context={"skills": [_EXTRACTED_SOLUTION_ARCHITECTURE]},
        config={"configurable": {"run_id": "run-3"}},
    )

    saved_skill = {
        **_EXTRACTED_SOLUTION_ARCHITECTURE,
        "requirement_level": 1.0,
    }
    mock_publish.assert_called_once()
    assert mock_publish.call_args.kwargs["context"]["skills"] == [saved_skill]
    assert mock_publish.call_args.kwargs["links"][0]["properties"] == {
        key: value for key, value in saved_skill.items() if key != "id"
    }


@patch.object(hub, "publish_skill_linked")
def test_publish_skill_linked_from_state_uses_jd_skills_when_context_omits_them(
    mock_publish: MagicMock,
) -> None:
    skill = JobDescriptionSkill.model_validate(_EXTRACTED_SOLUTION_ARCHITECTURE)
    hub.publish_skill_linked_from_state(
        {
            "jd_id": "jd-4",
            "user_id": "user-4",
            "jd": JobDescription(id="jd-4", skills=[skill]),
        },
        links=[],
        config={"configurable": {"run_id": "run-4"}},
    )

    mock_publish.assert_called_once()
    assert mock_publish.call_args.kwargs["context"]["skills"] == [
        skill.model_dump(mode="json")
    ]
    assert mock_publish.call_args.kwargs["context"]["skills"][0]["requirement_level"] == 1.0
    assert mock_publish.call_args.kwargs["context"]["skills"][0]["aliases"] == (
        _EXTRACTED_SOLUTION_ARCHITECTURE["aliases"]
    )


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


@patch.object(hub, "HubPublisher")
def test_publish_jd_gap_analysis_data(mock_hub_cls: MagicMock) -> None:
    publisher = MagicMock()
    mock_hub_cls.return_value = publisher

    hub.publish_jd_gap_analysis_data(
        job_description_id="jd-9",
        kind="gaps",
        data={"gaps": {"schema_version": 1}, "gaps_date": "2026-01-01T00:00:00+00:00"},
        job_id="session-1",
        user_id="user-9",
        run_id="run-9",
    )

    event = publisher.publish.call_args.args[0]
    assert event.type == LifecycleType.JD_GAP_ANALYSIS_DATA
    assert event.initiator == GraphId.GAP_COLLECT
    assert event.user_id == "user-9"
    assert event.payload.job_id == "session-1"
    assert event.payload.job_description_id == "jd-9"
    assert event.payload.run_id == "run-9"
    assert event.payload.kind == "gaps"
    assert event.payload.data["gaps"]["schema_version"] == 1


@patch.object(hub, "publish_jd_gap_analysis_data")
def test_publish_jd_gap_analysis_data_from_state(mock_publish: MagicMock) -> None:
    hub.publish_jd_gap_analysis_data_from_state(
        {
            "session_id": "sess-1",
            "job_description_id": "jd-4",
            "user_id": "user-4",
        },
        kind="gaps",
        data={"gaps": {}},
        config={"configurable": {"thread_id": "thread-4"}},
    )
    mock_publish.assert_called_once_with(
        job_description_id="jd-4",
        kind="gaps",
        data={"gaps": {}},
        job_id="sess-1",
        user_id="user-4",
        run_id="thread-4",
    )


@patch.object(hub, "HubPublisher")
def test_publish_jd_gap_analysis_end(mock_hub_cls: MagicMock) -> None:
    publisher = MagicMock()
    mock_hub_cls.return_value = publisher

    hub.publish_jd_gap_analysis_end(
        job_description_id="jd-9",
        job_id="session-1",
        user_id="user-9",
        run_id="run-9",
    )

    event = publisher.publish.call_args.args[0]
    assert event.type == LifecycleType.JD_GAP_ANALYSIS_END
    assert event.initiator == GraphId.GAP_COLLECT
    assert event.user_id == "user-9"
    assert event.payload.job_id == "session-1"
    assert event.payload.job_description_id == "jd-9"
    assert event.payload.run_id == "run-9"


@patch.object(hub, "publish_jd_gap_analysis_end")
def test_publish_jd_gap_analysis_end_from_state(mock_publish: MagicMock) -> None:
    hub.publish_jd_gap_analysis_end_from_state(
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


@patch.object(hub, "HubPublisher")
def test_publish_failure_propagates(mock_hub_cls: MagicMock) -> None:
    publisher = MagicMock()
    mock_hub_cls.return_value = publisher
    publisher.publish.side_effect = RuntimeError("sns failed")

    with pytest.raises(RuntimeError, match="sns failed"):
        hub.publish_jd_extraction_start(job_description_id="jd-1")

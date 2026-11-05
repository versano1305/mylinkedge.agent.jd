"""Unit tests for mark_done node."""

from __future__ import annotations

from unittest.mock import patch

from jd_agent.graphs.jd_extract.nodes import mark_done, resolve_company
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
    config = {"configurable": {"thread_id": "thread-7"}}
    state = {"jd_id": "jd-42", "jd": row}
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.publish_jd_extraction_end_from_state",
        ) as mock_publish,
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.emit_client_event",
        ) as mock_client_event,
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.emit_finish_interview",
        ) as mock_finish,
    ):
        result = mark_done(state, config)

    assert result == {"extraction_status": "done"}
    mock_publish.assert_called_once_with(
        state,
        skills=[
            {
                "id": None,
                "name": "Python",
                "requirement_level": 1.0,
                "source": "taxonomy",
            }
        ],
        sections={"requirements": "3+ years Python"},
        config=config,
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


def test_resolve_company_publishes_lookup() -> None:
    state = {
        "jd_id": "jd-42",
        "jd": JobDescription(id="jd-42", company_name="Acme"),
    }
    with patch(
        "jd_agent.graphs.jd_extract.nodes._legacy.publish_company_lookup_from_state",
    ) as mock_publish:
        result = resolve_company(state, {"configurable": {"run_id": "run-1"}})

    assert result == {}
    mock_publish.assert_called_once_with(
        state,
        company_name="Acme",
        config={"configurable": {"run_id": "run-1"}},
    )

"""Unit tests for mark_done node."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from mylinkedge_agent_tools.event_hub import (
    CompanyLookup,
    CompanyLookupResult,
    EventProcessingStatus,
)

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


def test_resolve_company_publishes_lookup_and_polls_status() -> None:
    state = {
        "jd_id": "jd-42",
        "jd": JobDescription(id="jd-42", company_name="Acme"),
    }
    publisher = MagicMock()
    status = MagicMock()
    status.is_terminal = True
    status.status = EventProcessingStatus.SUCCEEDED
    status.result_as.return_value = CompanyLookupResult.model_validate(
        {
            "resolved": [
                {
                    "query": {"label": "Company", "name": "Acme"},
                    "label": "Company",
                    "id": "c-1",
                    "element_id": "4:abc:1",
                    "name": "Acme Inc",
                }
            ],
            "unresolved": [],
        }
    )
    publisher.get_status.return_value = status

    with patch(
        "jd_agent.graphs.jd_extract.nodes._legacy.HubPublisher",
        return_value=publisher,
    ):
        result = resolve_company(state, {"configurable": {"run_id": "run-1"}})

    assert result == {"company_id": "c-1"}
    published = publisher.publish.call_args.args[0]
    assert isinstance(published, CompanyLookup)
    assert published.payload.nodes[0].name == "Acme"
    assert published.payload.context["job_description_id"] == "jd-42"
    assert published.payload.context["run_id"] == "run-1"
    publisher.get_status.assert_called_with(published.id)
    status.result_as.assert_called_once_with(CompanyLookupResult)


def test_resolve_company_raises_when_lookup_fails() -> None:
    state = {
        "jd_id": "jd-42",
        "jd": JobDescription(id="jd-42", company_name="Acme"),
    }
    publisher = MagicMock()
    status = SimpleNamespace(
        is_terminal=True,
        status=EventProcessingStatus.FAILED,
        error=SimpleNamespace(message="boom"),
        result_as=MagicMock(),
    )
    publisher.get_status.return_value = status

    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.HubPublisher",
            return_value=publisher,
        ),
        patch("jd_agent.graphs.jd_extract.nodes._legacy.time.sleep"),
        pytest.raises(RuntimeError, match="failed: boom"),
    ):
        resolve_company(state, {})

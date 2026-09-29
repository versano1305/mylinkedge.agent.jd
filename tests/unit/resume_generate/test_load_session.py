"""WU-01: load_session and mark_generating against a fake postgres backend."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from conftest import JD_ID, SESSION_ID, USER_ID, FakeUserResumeBuilders, make_session
from mylinkedge_agent_tools.taxonomy import TaxonomyGraph, TaxonomyNode

from jd_agent.graphs.resume_generate.constants import DEFAULT_TEMPLATE
from jd_agent.graphs.resume_generate.nodes import load_session, mark_generating
from jd_agent.graphs.resume_generate.taxonomy_types import MockTaxonomyTypes


@pytest.fixture(autouse=True)
def _taxonomy() -> Iterator[None]:
    graph = TaxonomyGraph(
        nodes={"person": TaxonomyNode(id="person", type="Person", name="Person")}
    )
    with MockTaxonomyTypes(graph):
        yield


def test_requires_session_id(fake_urb: FakeUserResumeBuilders) -> None:
    with pytest.raises(ValueError, match="session_id is required"):
        load_session({"session_id": "  "}, {})


def test_missing_session_raises(
    fake_urb: FakeUserResumeBuilders, owner_person_count: dict
) -> None:
    with pytest.raises(ValueError, match="No user_resume_builder row"):
        load_session({"session_id": "missing"}, {})


def test_unextracted_jd_raises(
    fake_urb: FakeUserResumeBuilders, owner_person_count: dict
) -> None:
    fake_urb.sessions[SESSION_ID] = make_session(extraction_status="extracting")
    with pytest.raises(ValueError, match="not extracted"):
        load_session({"session_id": SESSION_ID}, {})


def test_empty_user_id_raises(
    fake_urb: FakeUserResumeBuilders, owner_person_count: dict
) -> None:
    fake_urb.sessions[SESSION_ID] = make_session(user_id="")
    with pytest.raises(ValueError, match="has no user_id"):
        load_session({"session_id": SESSION_ID}, {})


def test_multiple_persons_per_owner_raises(
    fake_urb: FakeUserResumeBuilders, owner_person_count: dict
) -> None:
    owner_person_count["value"] = 2
    with pytest.raises(ValueError, match="2 Person nodes"):
        load_session({"session_id": SESSION_ID}, {})


@pytest.mark.parametrize("count", [0, 1])
def test_loads_session_scoped_by_owner(
    fake_urb: FakeUserResumeBuilders, owner_person_count: dict, count: int
) -> None:
    owner_person_count["value"] = count
    result = load_session({"session_id": SESSION_ID}, {})

    assert result["user_id"] == USER_ID
    assert result["session"].id == SESSION_ID
    assert result["jd"].extraction_status == "done"
    assert result["template"] == DEFAULT_TEMPLATE
    assert result["template"] is not DEFAULT_TEMPLATE
    assert result["generate_status"] == "generating"
    assert "person_id" not in result
    assert owner_person_count["calls"] == [(USER_ID, "Person")]


def test_mark_generating_updates_only_this_session(
    fake_urb: FakeUserResumeBuilders,
) -> None:
    mock_publisher = MagicMock()
    with patch(
        "jd_agent.graphs.resume_generate.nodes.mark_generating.node.ProcessEventPublisher",
        return_value=mock_publisher,
    ):
        result = mark_generating(
            {"session_id": SESSION_ID},
            {"configurable": {"thread_id": "thread-3"}},
        )

    assert fake_urb.status_updates == [(SESSION_ID, "template_in_progress")]
    assert result["session"].status == "template_in_progress"
    assert result["errors"] == []
    mock_publisher.publish.assert_called_once()
    event = mock_publisher.publish.call_args.args[0]
    assert event.type == "process.resume-generate/started"
    assert event.job_id == JD_ID
    assert event.trace_id == "thread-3"
    assert event.payload.model_dump() == {}

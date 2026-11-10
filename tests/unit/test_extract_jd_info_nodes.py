"""Unit tests for JD skills map-reduce nodes and dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Overwrite
from mylinkedge_agent_tools.event_hub import (
    EventProcessingStatus,
    EventStatus,
    EventStatusBatch,
    ExtractSkills,
    GraphId,
    LookupQuery,
    ResolvedNode,
)

from jd_agent.graphs.jd_extract.nodes.extract_jd_info.node import (
    collect_section_skill_results,
    extract_section_skills,
    route_section_skill_extraction,
    initialize_missing_skill_fields,
    prepare_jd_info_sections,
    save_jd_skills,
)
from jd_agent.graphs.jd_extract.state import JdExtractState
from jd_agent.integrations.supabase.jd_repository import JobDescription
from jd_agent.integrations.supabase.prompt_config_repository import PromptConfigRow

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_PARTITION_ROWS = [
    PromptConfigRow(
        id="1",
        type="jd_section_extraction",
        key="requirements",
        data={"heading": "Requirements", "section_description": "Must-haves"},
        sort_order=1,
        enabled=True,
    )
]


def test_route_section_skill_extraction() -> None:
    assert route_section_skill_extraction({"section_tasks": [{"section_key": "a"}]}) == (
        "extract_section_skills"
    )
    assert route_section_skill_extraction({"jd_id": "jd-1", "section_tasks": []}) == (
        "save_jd_skills"
    )


def test_prepare_jd_info_sections_builds_tasks() -> None:
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.client_from_env",
            return_value=MagicMock(),
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.list_by_type",
            return_value=_PARTITION_ROWS,
        ),
    ):
        result = prepare_jd_info_sections(
            {
                "jd_id": "jd-1",
                "jd": JobDescription(
                    id="jd-1",
                    sections={"requirements": "Need Go"},
                ),
            },
            {},
        )

    assert len(result["section_tasks"]) == 1
    task = result["section_tasks"][0]
    assert task["section_key"] == "requirements"
    assert task["section_content"] == "Need Go"
    assert task["prompt_config"]["key"] == "requirements"
    assert "process" not in task["prompt_config"]


def _make_task() -> dict:
    """Build a minimal ``section_task`` dict."""
    return {
        "section_key": "requirements",
        "section_content": "3+ years Python. Kubernetes preferred.",
        "sort_order": 1,
        "prompt_config": {
            "key": "requirements",
            "data": {"heading": "Requirements", "section_description": "Must-haves"},
        },
    }


_NODE = "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node"


def _resolved(
    *,
    skill_id: str,
    name: str,
    query_name: str | None = None,
    surface_form: str | None = None,
) -> ResolvedNode:
    query_name = query_name or name
    return ResolvedNode(
        query=LookupQuery(
            label="Skill",
            name=query_name,
            surface_form=surface_form,
        ),
        label="Skill",
        id=skill_id,
        element_id=f"4:{skill_id}:0",
        name=name,
    )


def _status(
    event_id: str,
    status: EventProcessingStatus = EventProcessingStatus.SUCCEEDED,
    resolved: list[ResolvedNode] | None = None,
    unresolved: list[LookupQuery] | None = None,
    error: dict | None = None,
) -> EventStatus:
    return EventStatus(
        event_id=event_id,
        status=status,
        topic="utility",
        type="extract_skills",
        initiator="jd_extract",
        result=(
            {
                "extracted_skills": [],
                "lookup_result": {
                    "resolved": [n.model_dump(mode="json") for n in resolved or []],
                    "unresolved": [q.model_dump(mode="json") for q in unresolved or []],
                },
            }
            if status == EventProcessingStatus.SUCCEEDED
            else None
        ),
        error=error,
    )


def test_extract_section_skills_publishes_one_event_per_section() -> None:
    with patch(f"{_NODE}.HubPublisher") as publisher_cls:
        result = extract_section_skills(
            {
                "jd_id": "jd-1",
                "user_id": "user-1",
                "section_tasks": [_make_task()],
            },
            {"configurable": {"run_id": "run-1"}},
        )

    event = publisher_cls.return_value.publish.call_args.args[0]
    assert isinstance(event, ExtractSkills)
    assert event.initiator == GraphId.JD_EXTRACT
    assert event.user_id == "user-1"
    assert event.payload.context == {
        "section_key": "requirements",
        "job_description_id": "jd-1",
        "run_id": "run-1",
    }
    refs = result["section_skill_extractions"]
    assert isinstance(refs, Overwrite)
    assert refs.value == [
        {"section_key": "requirements", "event_id": str(event.id)},
    ]


def test_extract_section_skills_skips_blank_sections() -> None:
    with patch(f"{_NODE}.HubPublisher") as publisher_cls:
        result = extract_section_skills(
            {
                "section_tasks": [
                    {**_make_task(), "section_content": "   "},
                    {**_make_task(), "section_key": "other", "section_content": "Go"},
                ]
            },
            {},
        )

    assert publisher_cls.return_value.publish.call_count == 1
    refs = result["section_skill_extractions"]
    assert isinstance(refs, Overwrite)
    assert refs.value[0]["section_key"] == "other"


def test_collect_section_skill_results_batches_and_filters_unresolved() -> None:
    python = _resolved(
        skill_id="skill-a",
        name="Python",
        surface_form="Python",
    )
    mystery = LookupQuery(label="Skill", name="Mystery Stack")
    sql = _resolved(skill_id="skill-b", name="SQL")
    client = MagicMock()
    client.get_many.side_effect = [
        EventStatusBatch(
            events=[
                _status("evt-1", resolved=[python], unresolved=[mystery]),
                _status("evt-2", EventProcessingStatus.PROCESSING),
            ],
        ),
        EventStatusBatch(events=[_status("evt-2", resolved=[sql])]),
    ]
    state = {
        "section_skill_extractions": [
            {"section_key": "requirements", "event_id": "evt-1"},
            {"section_key": "description", "event_id": "evt-2"},
        ]
    }

    with (
        patch(f"{_NODE}.EventStatusClient", return_value=client),
        patch(f"{_NODE}.time.sleep"),
    ):
        result = collect_section_skill_results(state, {})

    assert [call.args[0] for call in client.get_many.call_args_list] == [
        ["evt-1", "evt-2"],
        ["evt-2"],
    ]
    assert result["section_skill_extractions"] == Overwrite([])
    by_section = {r["section_key"]: r["skills"] for r in result["section_skill_results"]}
    assert by_section["requirements"] == [
        {"id": "skill-a", "name": "Python", "surface_form": "Python"}
    ]
    assert by_section["description"] == [
        {"id": "skill-b", "name": "SQL", "surface_form": "SQL"}
    ]


def test_collect_section_skill_results_raises_on_failed_event() -> None:
    client = MagicMock()
    client.get_many.return_value = EventStatusBatch(
        events=[
            _status(
                "evt-1",
                EventProcessingStatus.FAILED,
                error={"code": "handler_error", "message": "boom"},
            )
        ]
    )
    state = {
        "section_skill_extractions": [{"section_key": "requirements", "event_id": "evt-1"}]
    }

    with (
        patch(f"{_NODE}.EventStatusClient", return_value=client),
        pytest.raises(RuntimeError, match="boom"),
    ):
        collect_section_skill_results(state, {})


def test_collect_section_skill_results_times_out() -> None:
    client = MagicMock()
    client.get_many.return_value = EventStatusBatch(missing=["evt-1"])
    state = {
        "section_skill_extractions": [{"section_key": "requirements", "event_id": "evt-1"}]
    }

    with (
        patch(f"{_NODE}.EventStatusClient", return_value=client),
        patch(f"{_NODE}._SKILL_EXTRACT_TIMEOUT_SECONDS", 0.0),
        pytest.raises(TimeoutError, match="evt-1"),
    ):
        collect_section_skill_results(state, {})


def test_initialize_missing_skill_fields_applies_p1_fallbacks() -> None:
    result = initialize_missing_skill_fields(
        {
            "section_skill_results": [
                {
                    "section_key": "requirements",
                    "skills": [
                        {"id": "skill-a", "name": "Python"},
                        {
                            "id": "skill-b",
                            "name": "Kubernetes",
                            "surface_form": "k8s",
                            "evidence_sentence": "Kubernetes preferred.",
                            "importance": 0.5,
                            "substitutable": True,
                            "min_years": 2,
                        },
                    ],
                }
            ]
        },
        {},
    )

    assert result == {
        "section_skill_results": Overwrite(
            [
                {
                    "section_key": "requirements",
                    "skills": [
                        {
                            "id": "skill-a",
                            "name": "Python",
                            "surface_form": "Python",
                            "evidence_sentence": "",
                            "importance": 1.0,
                            "substitutable": False,
                            "min_years": None,
                        },
                        {
                            "id": "skill-b",
                            "name": "Kubernetes",
                            "surface_form": "k8s",
                            "evidence_sentence": "Kubernetes preferred.",
                            "importance": 0.5,
                            "substitutable": True,
                            "min_years": 2,
                        },
                    ],
                }
            ]
        )
    }


def test_save_jd_skills_merges_and_persists() -> None:
    state = {
        "jd_id": "jd-1",
        "section_skill_results": [
            {
                "section_key": "requirements",
                "skills": [
                    {"id": "skill-python", "name": "Python"},
                    {"name": "Go"},
                ],
            },
            {
                "section_key": "description",
                "skills": [
                    {"id": "skill-python", "name": "python"},
                    {"id": "skill-sql", "name": "SQL"},
                ],
            },
        ],
    }
    with patch(
        "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.publish_skill_linked_from_state",
    ) as publish_mock:
        result = save_jd_skills(state, {})

    publish_mock.assert_called_once()
    assert publish_mock.call_args.args[0] is state
    assert publish_mock.call_args.kwargs["links"] == [
        {
            "from_id": "jd-1",
            "relationship": "REQUIRES_SKILL",
            "to_id": "skill-python",
            "properties": {"name": "Python", "requirement_level": 1.0},
        },
        {
            "from_id": "jd-1",
            "relationship": "REQUIRES_SKILL",
            "to_id": "skill-sql",
            "properties": {"name": "SQL", "requirement_level": 1.0},
        },
    ]
    assert publish_mock.call_args.kwargs["context"]["skills"] == [
        {"id": "skill-python", "name": "Python", "requirement_level": 1.0},
        {"id": None, "name": "Go", "requirement_level": 1.0},
        {"id": "skill-sql", "name": "SQL", "requirement_level": 1.0},
    ]
    assert result == {
        "section_tasks": [],
        "section_skill_results": Overwrite([]),
    }
    assert "extraction" not in result


def test_map_reduce_subgraph_fans_out_and_merges() -> None:
    """Compile the skills subflow and prove parallel sections merge into save."""
    builder = StateGraph(JdExtractState)
    builder.add_node("prepare_jd_info_sections", prepare_jd_info_sections)
    builder.add_node("extract_section_skills", extract_section_skills)
    builder.add_node("collect_section_skill_results", collect_section_skill_results)
    builder.add_node("initialize_missing_skill_fields", initialize_missing_skill_fields)
    builder.add_node("save_jd_skills", save_jd_skills)
    builder.add_edge(START, "prepare_jd_info_sections")
    builder.add_conditional_edges(
        "prepare_jd_info_sections",
        route_section_skill_extraction,
        ["extract_section_skills", "save_jd_skills"],
    )
    builder.add_edge("extract_section_skills", "collect_section_skill_results")
    builder.add_edge("collect_section_skill_results", "initialize_missing_skill_fields")
    builder.add_edge("initialize_missing_skill_fields", "save_jd_skills")
    builder.add_edge("save_jd_skills", END)
    subgraph = builder.compile()

    partition_rows = [
        PromptConfigRow(
            id="1",
            type="jd_section_extraction",
            key="requirements",
            data={"heading": "Requirements"},
            sort_order=1,
            enabled=True,
        ),
        PromptConfigRow(
            id="2",
            type="jd_section_extraction",
            key="description",
            data={"heading": "Description"},
            sort_order=2,
            enabled=True,
        ),
    ]

    skill = _resolved(
        skill_id="skill-a",
        name="Python",
        surface_form="Python",
    )
    status_client = MagicMock()
    status_client.get_many.side_effect = lambda ids: EventStatusBatch(
        events=[_status(event_id, resolved=[skill]) for event_id in ids]
    )

    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.client_from_env",
            return_value=MagicMock(),
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.list_by_type",
            return_value=partition_rows,
        ),
        patch(f"{_NODE}.HubPublisher") as publisher_cls,
        patch(f"{_NODE}.EventStatusClient", return_value=status_client),
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.publish_skill_linked_from_state",
        ) as publish_mock,
    ):
        result = subgraph.invoke(
            {
                "jd_id": "jd-1",
                "jd": JobDescription(
                    id="jd-1",
                    sections={
                        "requirements": "Need Python",
                        "description": "Build services",
                    },
                ),
            }
        )

    assert publisher_cls.return_value.publish.call_count == 2
    status_client.get_many.assert_called_once()
    publish_mock.assert_called_once()
    assert publish_mock.call_args.kwargs["links"] == [
        {
            "from_id": "jd-1",
            "relationship": "REQUIRES_SKILL",
            "to_id": "skill-a",
            "properties": {
                "name": "Python",
                "requirement_level": 1.0,
                "surface_form": "Python",
                "evidence_sentence": "",
                "importance": 1.0,
                "substitutable": False,
                "min_years": None,
            },
        }
    ]
    assert result["section_tasks"] == []
    assert result["section_skill_results"] == []
    assert "extraction" not in result

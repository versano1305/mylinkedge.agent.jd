"""Unit tests for JD skills map-reduce nodes and dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from langgraph.graph import END, START, StateGraph
from langgraph.types import Overwrite, Send
from mylinkedge_agent_tools.skill_matching import ExtractedSkill

from jd_agent.graphs.jd_extract.nodes.extract_jd_info.node import (
    dispatch_section_skill_tasks,
    extract_section_skills,
    initialize_missing_skill_fields,
    prepare_jd_info_sections,
    save_jd_skills,
)
from jd_agent.graphs.jd_extract.state import JdExtractState
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


def test_dispatch_returns_send_per_section_task() -> None:
    state = {
        "jd_id": "jd-1",
        "section_tasks": [
            {
                "section_key": "requirements",
                "section_content": "Python",
                "prompt_config": {"key": "requirements"},
                "sort_order": 1,
            },
            {
                "section_key": "description",
                "section_content": "Build APIs",
                "prompt_config": {"key": "description"},
                "sort_order": 0,
            },
        ],
    }

    result = dispatch_section_skill_tasks(state)

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(item, Send) for item in result)
    assert all(item.node == "extract_section_skills" for item in result)
    assert result[0].arg["section_task"]["section_key"] == "requirements"
    assert "section_task" in result[1].arg
    assert "jd_id" not in result[1].arg


def test_dispatch_skips_to_save_when_no_tasks() -> None:
    assert dispatch_section_skill_tasks({"jd_id": "jd-1", "section_tasks": []}) == (
        "save_jd_skills"
    )


def test_prepare_jd_info_sections_builds_tasks() -> None:
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.client_from_env",
            return_value=MagicMock(),
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.jd_repo.get_sections",
            return_value={"requirements": "Need Go"},
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.list_by_type",
            return_value=_PARTITION_ROWS,
        ),
    ):
        result = prepare_jd_info_sections({"jd_id": "jd-1"}, {})

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


def test_extract_section_skills_calls_tool_on_full_section_text() -> None:
    """extract_section_skills passes section content once and packages results."""
    skill_a = ExtractedSkill(
        id="skill-a",
        name="Python",
        description="",
        evidence_sentence="3+ years Python.",
        surface_form="Python",
    )
    skill_b = ExtractedSkill(
        id="skill-b",
        name="Kubernetes",
        description="",
        evidence_sentence="Kubernetes preferred.",
        surface_form="Kubernetes",
    )
    task = _make_task()

    with patch(
        "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.relevant_skills_from_text",
        return_value=[skill_a, skill_b],
    ) as mock_match:
        config = {"run_name": "test-extract"}
        result = extract_section_skills({"section_task": task}, config)

    mock_match.assert_called_once_with(task["section_content"], config=config)
    assert result == {
        "section_skill_results": [
            {
                "section_key": "requirements",
                "skills": [
                    {
                        "id": "skill-a",
                        "name": "Python",
                        "skill_type": "unknown",
                        "type": "Skill",
                        "aliases": [],
                        "properties": {},
                        "is_existing": True,
                        "evidence_sentence": "3+ years Python.",
                        "surface_form": "Python",
                        "candidate_ids": [],
                    },
                    {
                        "id": "skill-b",
                        "name": "Kubernetes",
                        "skill_type": "unknown",
                        "type": "Skill",
                        "aliases": [],
                        "properties": {},
                        "is_existing": True,
                        "evidence_sentence": "Kubernetes preferred.",
                        "surface_form": "Kubernetes",
                        "candidate_ids": [],
                    },
                ],
            }
        ]
    }


def test_extract_section_skills_filters_unresolved_skills() -> None:
    resolved = ExtractedSkill(
        id="skill-a",
        name="Python",
        evidence_sentence="Need Python",
        surface_form="Python",
    )
    unresolved = ExtractedSkill(
        name="Mystery Stack",
        evidence_sentence="Need Mystery Stack",
        surface_form="Mystery Stack",
    )

    with patch(
        "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.relevant_skills_from_text",
        return_value=[resolved, unresolved],
    ):
        result = extract_section_skills({"section_task": _make_task()}, {})

    skills = result["section_skill_results"][0]["skills"]
    assert [skill["name"] for skill in skills] == ["Python"]
    assert all(skill["is_existing"] for skill in skills)


def test_extract_section_skills_returns_empty_for_blank_section() -> None:
    task = {**_make_task(), "section_content": "   "}

    with patch(
        "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.relevant_skills_from_text",
    ) as mock_match:
        result = extract_section_skills({"section_task": task}, {})

    mock_match.assert_not_called()
    assert result == {
        "section_skill_results": [{"section_key": "requirements", "skills": []}]
    }


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
                "skills": [{"name": "Python"}, {"name": "Go"}],
            },
            {
                "section_key": "description",
                "skills": [{"name": "python"}, {"name": "SQL"}],
            },
        ],
    }
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.client_from_env",
            return_value=MagicMock(),
        ) as client_mock,
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.jd_repo.upsert_skills",
        ) as upsert_mock,
    ):
        result = save_jd_skills(state, {})

    upsert_mock.assert_called_once()
    assert upsert_mock.call_args.args[0] is client_mock.return_value
    assert upsert_mock.call_args.args[1] == "jd-1"
    assert upsert_mock.call_args.kwargs["skills"] == [
        {"name": "Python"},
        {"name": "Go"},
        {"name": "SQL"},
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
    builder.add_node("initialize_missing_skill_fields", initialize_missing_skill_fields)
    builder.add_node("save_jd_skills", save_jd_skills)
    builder.add_edge(START, "prepare_jd_info_sections")
    builder.add_conditional_edges(
        "prepare_jd_info_sections",
        dispatch_section_skill_tasks,
        ["extract_section_skills", "save_jd_skills"],
    )
    builder.add_edge("extract_section_skills", "initialize_missing_skill_fields")
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

    skill = ExtractedSkill(
        id="skill-a",
        name="Python",
        description="",
        evidence_sentence="Need Python",
        surface_form="Python",
    )

    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.client_from_env",
            return_value=MagicMock(),
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.jd_repo.get_sections",
            return_value={
                "requirements": "Need Python",
                "description": "Build services",
            },
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.list_by_type",
            return_value=partition_rows,
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.relevant_skills_from_text",
            return_value=[skill],
        ) as match_mock,
        patch(
            "jd_agent.graphs.jd_extract.nodes.extract_jd_info.node.jd_repo.upsert_skills",
        ) as upsert_mock,
    ):
        result = subgraph.invoke({"jd_id": "jd-1"})

    assert match_mock.call_count == 2
    upsert_mock.assert_called_once()
    assert upsert_mock.call_args.kwargs["skills"] == [
        {
            "id": "skill-a",
            "name": "Python",
            "skill_type": "unknown",
            "type": "Skill",
            "aliases": [],
            "properties": {},
            "is_existing": True,
            "evidence_sentence": "Need Python",
            "surface_form": "Python",
            "candidate_ids": [],
            "importance": 1.0,
            "substitutable": False,
            "min_years": None,
        }
    ]
    assert result["section_tasks"] == []
    assert result["section_skill_results"] == []
    assert "extraction" not in result

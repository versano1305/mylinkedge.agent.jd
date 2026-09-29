"""Unit tests for gap-collect JD target loading."""

from __future__ import annotations

import pytest

from jd_agent.graphs.gap_collect.nodes.load_jd_targets import node as load_jd_targets_node
from jd_agent.graphs.gap_collect.nodes.load_jd_targets.node import load_jd_targets
from jd_agent.integrations.supabase.jd_repository import (
    JobDescription,
    JobDescriptionSkill,
    normalize_job_description,
)


def test_normalize_job_description_keeps_id_only_skills() -> None:
    row = normalize_job_description(
        {
            "id": "jd-1",
            "skills": [
                {"id": "skill-1", "requirement_level": 0.25},
                {"requirement_level": 0.5},
                {"name": "Python"},
            ],
        }
    )

    assert [(skill.id, skill.name, skill.requirement_level) for skill in row.skills] == [
        ("skill-1", "", 0.25),
        (None, "Python", 1.0),
    ]


def test_load_jd_targets_uses_graph_fields_and_clamps_requirement_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_fetch(skill_ids: list[str], fields: tuple[str, ...]) -> dict[str, dict[str, str]]:
        captured["ids"] = list(skill_ids)
        captured["fields"] = fields
        return {
            "skill-a": {"id": "skill-a", "name": "Alpha", "skillType": "Tool"},
        }

    monkeypatch.setattr(load_jd_targets_node, "fetch_skills_by_ids", fake_fetch)
    jd = JobDescription(
        id="jd-1",
        skills=[
            JobDescriptionSkill(
                id="skill-a",
                name="Ignored Name",
                requirement_level=0.2,
            ),
            JobDescriptionSkill(id="skill-a", requirement_level=0.8),
            JobDescriptionSkill(id="missing", name="Stored", requirement_level=1.5),
            JobDescriptionSkill(name="no-id", requirement_level=0.1),
            JobDescriptionSkill(id="skill-b", requirement_level=-1),
        ],
    )

    result = load_jd_targets({"jd": jd}, {})

    assert captured["fields"] == ("id", "name", "skillType")
    assert captured["ids"] == ["skill-a", "missing", "skill-b"]
    assert result["jd_raw_skills"] == [
        {
            "id": "skill-a",
            "name": "Alpha",
            "skillType": "Tool",
            "requirement_level": 0.8,
        },
        {
            "id": "missing",
            "name": "",
            "skillType": "",
            "requirement_level": 1.0,
        },
        {
            "id": "skill-b",
            "name": "",
            "skillType": "",
            "requirement_level": 0.0,
        },
    ]


def test_load_jd_targets_requires_a_skill_id() -> None:
    jd = JobDescription(id="jd-1", skills=[JobDescriptionSkill(name="Python")])
    with pytest.raises(ValueError, match="no ids"):
        load_jd_targets({"jd": jd}, {})

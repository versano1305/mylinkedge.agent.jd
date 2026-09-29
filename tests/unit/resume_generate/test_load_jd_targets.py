"""WU-03: resolve JD skills into weighted targets, domains, and context."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from mylinkedge_agent_tools.postgres import JobDescription, JobDescriptionSkill

from jd_agent.graphs.resume_generate.nodes.load_jd_targets.node import load_jd_targets

_NODE = importlib.import_module("jd_agent.graphs.resume_generate.nodes.load_jd_targets.node")

_GRAPH = SimpleNamespace(
    nodes={
        "skill-python": SimpleNamespace(name="Python", skill_type="Language"),
        "skill-k8s": SimpleNamespace(name="Kubernetes", skill_type="Tool"),
        "skill-fintech": SimpleNamespace(name="Fintech", skill_type="Domain"),
    }
)


def _jd(**overrides: object) -> JobDescription:
    payload: dict[str, object] = {
        "id": "jd-1",
        "title_name": "Cloud Architect",
        "company_name": "Acme",
        "skills": [JobDescriptionSkill(id="skill-python", name="Python")],
    }
    payload.update(overrides)
    return JobDescription.model_validate(payload)


@pytest.fixture
def skills_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_NODE, "get_skills_graph", lambda: _GRAPH)


def test_requires_loaded_jd() -> None:
    with pytest.raises(ValueError, match="jd must be loaded"):
        load_jd_targets({}, {})


def test_empty_skills_raises(skills_graph: None) -> None:
    jd = _jd(skills=[])
    with pytest.raises(ValueError, match="no extracted skills"):
        load_jd_targets({"jd": jd}, {})


def test_bare_skill_defaults_importance_and_enrichment(skills_graph: None) -> None:
    result = load_jd_targets({"jd": _jd()}, {})

    assert result["jd_targets"] == [
        {
            "skill_id": "skill-python",
            "name": "Python",
            "surface_form": "Python",
            "skill_type": "Language",
            "importance": 1.0,
            "weight": 1.0,
            "min_years": None,
            "substitutable": False,
            "evidence_sentence": "",
        }
    ]
    assert result["jd_domains"] == []
    assert result["jd_context"]["title"] == "Cloud Architect"
    assert result["jd_context"]["company_name"] == "Acme"
    assert result["jd_context"]["unresolved"] == []


def test_enriched_skill_keeps_importance_float(skills_graph: None) -> None:
    jd = _jd(
        skills=[
            JobDescriptionSkill.model_validate(
                {
                    "id": "skill-k8s",
                    "name": "Kubernetes",
                    "surface_form": "k8s",
                    "evidence_sentence": "Kubernetes preferred.",
                    "importance": 0.5,
                    "substitutable": True,
                    "min_years": 2,
                }
            )
        ]
    )

    result = load_jd_targets({"jd": jd}, {})

    row = result["jd_targets"][0]
    assert row["skill_id"] == "skill-k8s"
    assert row["name"] == "Kubernetes"
    assert row["surface_form"] == "k8s"
    assert row["importance"] == 0.5
    assert row["weight"] == 0.5
    assert row["substitutable"] is True
    assert row["min_years"] == 2
    assert row["evidence_sentence"] == "Kubernetes preferred."


def test_importance_is_clamped_and_non_numeric_falls_back(skills_graph: None) -> None:
    jd = _jd(
        skills=[
            JobDescriptionSkill.model_validate(
                {"id": "skill-python", "name": "Python", "importance": 1.4}
            ),
            JobDescriptionSkill.model_validate(
                {"id": "skill-k8s", "name": "Kubernetes", "importance": "must"}
            ),
        ]
    )

    result = load_jd_targets({"jd": jd}, {})
    by_id = {row["skill_id"]: row for row in result["jd_targets"]}

    assert by_id["skill-python"]["importance"] == 1.0
    assert by_id["skill-k8s"]["importance"] == 1.0
    assert by_id["skill-k8s"]["weight"] == 1.0


def test_domain_skills_are_split_out(skills_graph: None) -> None:
    jd = _jd(
        skills=[
            JobDescriptionSkill(id="skill-python", name="Python"),
            JobDescriptionSkill(id="skill-fintech", name="Fintech"),
        ]
    )

    result = load_jd_targets({"jd": jd}, {})

    assert [row["skill_id"] for row in result["jd_targets"]] == ["skill-python"]
    assert [row["skill_id"] for row in result["jd_domains"]] == ["skill-fintech"]
    assert result["jd_domains"][0]["skill_type"] == "Domain"


def test_unresolved_names_stay_out_of_targets(skills_graph: None) -> None:
    jd = _jd(
        skills=[
            JobDescriptionSkill(id="skill-python", name="Python"),
            JobDescriptionSkill(name="Mystery Stack"),
        ]
    )

    result = load_jd_targets({"jd": jd}, {})

    assert [row["skill_id"] for row in result["jd_targets"]] == ["skill-python"]
    assert result["jd_context"]["unresolved"] == ["Mystery Stack"]


def test_all_unresolved_returns_empty_targets(skills_graph: None) -> None:
    jd = _jd(skills=[JobDescriptionSkill(name="Mystery Stack")])

    result = load_jd_targets({"jd": jd}, {})

    assert result["jd_targets"] == []
    assert result["jd_domains"] == []
    assert result["jd_context"]["unresolved"] == ["Mystery Stack"]


def test_resolves_by_casefolded_name_when_id_misses(skills_graph: None) -> None:
    jd = _jd(skills=[JobDescriptionSkill(id="missing", name="python")])

    result = load_jd_targets({"jd": jd}, {})

    assert result["jd_targets"][0]["skill_id"] == "skill-python"
    assert result["jd_targets"][0]["name"] == "Python"
    assert result["jd_targets"][0]["surface_form"] == "python"


def test_duplicate_ids_keep_first_text_and_max_importance(skills_graph: None) -> None:
    jd = _jd(
        skills=[
            JobDescriptionSkill.model_validate(
                {
                    "id": "skill-python",
                    "name": "Python",
                    "surface_form": "Python",
                    "importance": 0.4,
                    "evidence_sentence": "first",
                }
            ),
            JobDescriptionSkill.model_validate(
                {
                    "id": "skill-python",
                    "name": "Python",
                    "surface_form": "py",
                    "importance": 0.9,
                    "evidence_sentence": "second",
                }
            ),
        ]
    )

    result = load_jd_targets({"jd": jd}, {})

    assert len(result["jd_targets"]) == 1
    row = result["jd_targets"][0]
    assert row["surface_form"] == "Python"
    assert row["evidence_sentence"] == "first"
    assert row["importance"] == 0.9
    assert row["weight"] == 0.9


def test_requirements_from_canonical_sections(skills_graph: None) -> None:
    jd = _jd(
        sections={
            "canonical": {
                "sections": [{"section_type": "requirements", "content": "  7+ years Python.  "}]
            },
            "requirements": "flat text should be ignored",
        }
    )

    result = load_jd_targets({"jd": jd}, {})

    assert result["jd_context"]["requirements"] == "7+ years Python."


def test_requirements_fall_back_to_flat_field(skills_graph: None) -> None:
    jd = _jd(sections={"requirements": "  Familiarity with AWS.  "})

    result = load_jd_targets({"jd": jd}, {})

    assert result["jd_context"]["requirements"] == "Familiarity with AWS."

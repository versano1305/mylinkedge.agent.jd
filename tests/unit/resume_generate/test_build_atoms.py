"""Unit tests for WU-05 build_atoms."""

from __future__ import annotations

import pytest

from jd_agent.graphs.resume_generate.models import Dossier, EvidenceEntry, Instance, SkillRef
from jd_agent.graphs.resume_generate.nodes.build_atoms.from_dossier import (
    build_atoms_from_dossier,
)
from jd_agent.graphs.resume_generate.nodes.build_atoms.node import build_atoms
from jd_agent.graphs.resume_generate.taxonomy_types import MockTaxonomyTypes
from mylinkedge_agent_tools.taxonomy import TaxonomyGraph, TaxonomyNode, TaxonomyEdge


def _taxonomy() -> TaxonomyGraph:
    return TaxonomyGraph(
        nodes={
            "experience": TaxonomyNode(
                id="experience", type="ExperienceEvent", name="ExperienceEvent"
            ),
            "achievement": TaxonomyNode(
                id="achievement", type="Achievement", name="Achievement"
            ),
            "project": TaxonomyNode(id="project", type="Project", name="Project"),
            "mentorship": TaxonomyNode(
                id="mentorship", type="Mentorship", name="Mentorship"
            ),
            "skill": TaxonomyNode(id="skill", type="Skill", name="Skill"),
        },
        edges=[
            TaxonomyEdge(
                id="exp|uses|skill",
                source="experience",
                target="skill",
                type="USES_SKILL",
                source_name="ExperienceEvent",
                target_name="Skill",
            ),
        ],
    )


@pytest.fixture
def taxonomy_ctx():
    with MockTaxonomyTypes(_taxonomy()):
        yield


def test_achievement_atom_uses_desc_and_metrics(taxonomy_ctx) -> None:
    dossier = Dossier(
        user_id="u1",
        instances=[
            Instance(
                instance_id="exp1",
                node_label="ExperienceEvent",
                end="2023-06",
            ),
            Instance(
                instance_id="ach1",
                node_label="Achievement",
                parent_instance_id="exp1",
                summary="Reduced spend by 30%.",
                impact_value="30%",
                skills=[SkillRef(id="s1", name="AWS")],
            ),
        ],
    )
    atoms = build_atoms_from_dossier(dossier)
    ach = next(a for a in atoms if a.atom_id == "ach:ach1")
    assert ach.kind == "achievement"
    assert "30%" in ach.metrics
    assert ach.skill_ids == ["s1"]
    assert ach.end == "2023-06"


def test_summary_skill_attachment_and_context_bucket(taxonomy_ctx) -> None:
    dossier = Dossier(
        user_id="u1",
        instances=[
            Instance(
                instance_id="exp1",
                node_label="ExperienceEvent",
                summary="Built microservices on AWS. Mentored junior engineers.",
                skills=[
                    SkillRef(
                        id="aws",
                        evidence=[
                            EvidenceEntry(
                                evidenceText="Built microservices on AWS",
                                sourceKind="resume",
                            )
                        ],
                    ),
                    SkillRef(id="orphan", evidence=[]),
                ],
            ),
        ],
    )
    atoms = build_atoms_from_dossier(dossier)
    by_id = {a.atom_id: a for a in atoms}
    assert "sum:exp1#1" in by_id
    assert "aws" in by_id["sum:exp1#1"].skill_ids
    ctx = by_id["ctx:exp1"]
    assert "orphan" in ctx.skill_ids
    assert ctx.text == ""

    all_skills = set()
    for a in atoms:
        if a.instance_id == "exp1" and a.kind == "summary_sentence":
            all_skills.update(a.skill_ids)
    assert all_skills == {"aws", "orphan"}


def test_dedupe_sentence_when_achievement_overlaps(taxonomy_ctx) -> None:
    dossier = Dossier(
        user_id="u1",
        instances=[
            Instance(
                instance_id="exp1",
                node_label="ExperienceEvent",
                summary="Reduced spend by 30% across the platform.",
                skills=[
                    SkillRef(
                        id="fin",
                        evidence=[
                            EvidenceEntry(
                                evidenceText="Reduced spend by 30%",
                                sourceKind="resume",
                            )
                        ],
                    ),
                ],
            ),
            Instance(
                instance_id="ach1",
                node_label="Achievement",
                parent_instance_id="exp1",
                summary="Reduced spend by 30% across the platform.",
                impact_value="30%",
            ),
        ],
    )
    atoms = build_atoms_from_dossier(dossier)
    sentence_atoms = [
        a for a in atoms if a.kind == "summary_sentence" and a.text
    ]
    assert sentence_atoms == []
    ctx = next((a for a in atoms if a.atom_id == "ctx:exp1"), None)
    assert ctx is not None
    assert "fin" in ctx.skill_ids


def test_build_atoms_node(taxonomy_ctx) -> None:
    result = build_atoms(
        {
            "dossier": {
                "user_id": "u1",
                "instances": [
                    {
                        "instance_id": "exp1",
                        "node_label": "ExperienceEvent",
                        "summary": "Hello world.",
                    }
                ],
            }
        },
        {},
    )
    assert len(result["atoms"]) >= 1


def test_build_atoms_requires_dossier() -> None:
    with pytest.raises(ValueError, match="dossier"):
        build_atoms({}, {})

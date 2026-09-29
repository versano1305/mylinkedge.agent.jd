"""Tests that the resume generation graph compiles and runs end to end on stubs."""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

from conftest import SESSION_ID, USER_ID, FakeUserResumeBuilders
from mylinkedge_agent_tools.postgres import JobDescriptionSkill
from mylinkedge_agent_tools.taxonomy import TaxonomyGraph, TaxonomyNode

from jd_agent.graphs.resume_generate.models import Dossier, ResumeTrace
from jd_agent.graphs.resume_generate.resume_generate_graph import graph
from jd_agent.graphs.resume_generate.taxonomy_types import MockTaxonomyTypes

_TAXONOMY = TaxonomyGraph(
    nodes={
        "person": TaxonomyNode(id="person", type="Person", name="Person"),
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
    }
)

_EXPECTED_NODES = (
    "load_session",
    "mark_generating",
    "load_dossier",
    "load_jd_targets",
    "score_demand",
    "build_atoms",
    "license_and_value",
    "allocate",
    "build_briefs",
    "generate_highlights",
    "generate_summary",
    "verify",
    "assemble_and_save",
    "mark_done",
)


def test_resume_generate_graph_compiles() -> None:
    assert graph is not None
    assert graph.name == "resume-generate"


def test_resume_generate_graph_has_expected_nodes() -> None:
    node_names = set(graph.get_graph().nodes)
    for name in _EXPECTED_NODES:
        assert name in node_names


def test_resume_generate_smoke_minimum_invoke_returns_schema_valid_resume(
    fake_urb: FakeUserResumeBuilders, owner_person_count: dict, monkeypatch
) -> None:
    """Full graph invoke with only ``{"session_id": ...}`` (no Neo4j / Supabase)."""
    loaded = fake_urb.sessions[SESSION_ID]
    loaded.job_description.skills = [JobDescriptionSkill(id="skill-aws", name="AWS")]
    fake_skills_graph = SimpleNamespace(
        nodes={"skill-aws": SimpleNamespace(name="AWS", skill_type="Tool")},
        edges=[],
    )
    jd_targets_node = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.load_jd_targets.node"
    )
    score_demand_node = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.score_demand.node"
    )
    allocate_node = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.allocate.node"
    )
    build_briefs_node = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.build_briefs.node"
    )
    dossier_node = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.load_dossier.node"
    )
    highlights_agent = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.generate_highlights.agent"
    )
    summary_agent = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.generate_summary.agent"
    )
    verify_node = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.verify.node"
    )
    license_node = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.license_and_value.node"
    )
    monkeypatch.setattr(jd_targets_node, "get_skills_graph", lambda: fake_skills_graph)
    monkeypatch.setattr(license_node, "get_skills_graph", lambda: fake_skills_graph)
    monkeypatch.setattr(score_demand_node, "get_skills_graph", lambda: fake_skills_graph)
    monkeypatch.setattr(allocate_node, "get_skills_graph", lambda: fake_skills_graph)
    monkeypatch.setattr(build_briefs_node, "get_skills_graph", lambda: fake_skills_graph)
    monkeypatch.setattr(verify_node, "get_skills_graph", lambda: fake_skills_graph)
    monkeypatch.setattr(
        dossier_node,
        "fetch_candidate_dossier",
        lambda user_id: Dossier(user_id=user_id),
    )
    from jd_agent.graphs.resume_generate.nodes.generate_highlights.models import (
        HighlightGenerationResult,
    )

    monkeypatch.setattr(
        highlights_agent,
        "generate_for_brief",
        lambda *args, **kwargs: HighlightGenerationResult(
            summary="",
            highlights=[],
        ),
    )
    from jd_agent.graphs.resume_generate.models import SummaryResult

    monkeypatch.setattr(
        summary_agent,
        "generate_summary_llm",
        lambda *args, **kwargs: SummaryResult(),
    )
    mark_generating_node = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.mark_generating.node"
    )
    mark_done_node = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.mark_done.node"
    )
    monkeypatch.setattr(mark_generating_node, "ProcessEventPublisher", MagicMock)
    monkeypatch.setattr(mark_done_node, "ProcessEventPublisher", MagicMock)
    with MockTaxonomyTypes(_TAXONOMY):
        result = asyncio.run(graph.ainvoke({"session_id": SESSION_ID}))

    assert result["user_id"] == USER_ID
    assert fake_urb.status_updates == [(SESSION_ID, "template_in_progress")]
    assert len(fake_urb.saved_resumes) == 1
    saved_id, saved_resume, saved_trace = fake_urb.saved_resumes[0]
    assert saved_id == SESSION_ID
    assert saved_resume["$schema"].endswith("schema.json")
    assert saved_trace["schema_version"] == 1

    resume = result["resume"]
    assert resume["$schema"].endswith("schema.json")
    assert "basics" in resume
    assert resume.get("work", []) == []
    assert resume.get("skills", []) == []

    demand = result.get("demand")
    assert isinstance(demand, dict)
    assert demand.get("fit_profile") is not None
    assert demand.get("listed_jd_skill_ids") == ["skill-aws"]

    trace = ResumeTrace.model_validate(result["trace"])
    assert trace.schema_version == 1
    assert trace.meta.user_id == USER_ID
    assert result["generate_status"] == "done"

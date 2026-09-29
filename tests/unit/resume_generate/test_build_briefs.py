"""Tests for WU-08 build_briefs."""

from __future__ import annotations

from types import SimpleNamespace
import importlib

from jd_agent.graphs.resume_generate.models import Allocation
from jd_agent.graphs.resume_generate.nodes.build_briefs.pipeline import run_build_briefs
from jd_agent.graphs.resume_generate.nodes.allocate.pipeline import run_allocation
from jd_agent.shared import skill_closures as closures

SKILL_META = {
    "A": {"name": "Microservices", "skillType": "Capability"},
    "B": {"name": "Docker", "skillType": "Tool"},
}
EDGES = [("A", "B", "USES")]


def _is_domain(skill_id: str) -> bool:
    return closures.make_is_domain(SKILL_META)(skill_id)


def _exp(instance_id: str, *, end: str | None = "2024-01", position: str = "Engineer") -> dict:
    return {
        "instance_id": instance_id,
        "node_label": "ExperienceEvent",
        "company": "Acme",
        "position": position,
        "position_aliases": ["Platform Engineer"],
        "company_description": "Enterprise SaaS.",
        "start": "2020-01",
        "end": end,
        "skills": [{"id": "A", "name": "Microservices", "skillType": "Capability"}],
    }


def _atom(atom_id: str, exp_id: str) -> dict:
    return {
        "atom_id": atom_id,
        "instance_id": exp_id,
        "kind": "achievement",
        "text": "Shipped microservices.",
        "skill_ids": ["A"],
        "metrics": ["40%"],
        "strength": 1.0,
        "licensed": [
            {
                "jd_skill_id": "A",
                "surface_form": "Microservices",
                "via": "explicit",
            }
        ],
    }


def test_build_briefs_budget_matches_selected_not_tier_cap() -> None:
    d_star = closures.demand_closure({"A": 1.0}, EDGES, _is_domain)
    demand = {
        "d_star": d_star,
        "weights": {k: 1.0 for k in d_star},
        "s_star_profile": {k: 0.5 for k in d_star},
        "edges_subset": EDGES,
    }
    dossier = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "instances": [_exp("exp-1")],
        "raw_educations": [],
        "certificates": [],
        "languages": [],
        "awards": [],
        "publications": [],
        "volunteer": [],
        "skills": [],
    }
    atoms = [_atom("a1", "exp-1"), _atom("a2", "exp-1")]
    allocation = run_allocation(
        dossier,
        atoms,
        demand,
        {"page_budget": 2, "max_highlights_total": 5},
        {"title": "Microservices Engineer"},
        EDGES,
        _is_domain,
    )
    briefs = run_build_briefs(
        dossier,
        allocation,
        atoms,
        demand,
        [{"skill_id": "A", "name": "Microservices", "surface_form": "Microservices", "weight": 1.0, "importance": "must"}],
        {"title": "Microservices Engineer"},
        EDGES,
        SKILL_META,
    )
    brief = briefs["instances"]["exp-1"]
    assert brief["budget"] == len(allocation.selected["exp-1"])
    assert brief["budget"] <= allocation.budgets["exp-1"]
    assert brief["company_description"] == "Enterprise SaaS."
    assert brief["atoms"][0]["licensed"] == ["Microservices"]
    assert briefs["static"]["basics"]["name"] == "Ada Lovelace"
    assert briefs["static"]["skills"]
    assert "Microservices" in briefs["skills_sources"]
    assert briefs["generatable_instance_ids"] == ["exp-1"]


def test_build_briefs_node_requires_allocation(monkeypatch) -> None:
    node_mod = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.build_briefs.node"
    )

    def _fake_graph():
        nodes = {
            nid: SimpleNamespace(name=meta["name"], skill_type=meta["skillType"])
            for nid, meta in SKILL_META.items()
        }
        edge_objs = [SimpleNamespace(source=s, target=t, type=ty) for s, t, ty in EDGES]
        return SimpleNamespace(nodes=nodes, edges=edge_objs)

    monkeypatch.setattr(node_mod, "get_skills_graph", _fake_graph)

    d_star = closures.demand_closure({"A": 1.0}, EDGES, _is_domain)
    state = {
        "dossier": {"instances": []},
        "allocation": Allocation().model_dump(),
        "demand": {"d_star": d_star, "weights": {"A": 1.0}, "s_star_profile": {"A": 0.5}},
        "atoms": [],
        "jd_targets": [],
        "jd_context": {"title": "Engineer"},
    }
    out = node_mod.build_briefs(state, {})
    assert "name" not in out["briefs"]["static"]["basics"]

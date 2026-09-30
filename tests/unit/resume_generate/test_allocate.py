"""Tests for WU-07 atom allocation."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import importlib
import pytest

from jd_agent.graphs.resume_generate.models import Allocation
from jd_agent.graphs.resume_generate.nodes.allocate.pipeline import run_allocation
from jd_agent.graphs.resume_generate.nodes.allocate.work_instances import months_since_end
from jd_agent.shared import skill_closures as closures

SKILL_META = {
    "A": {"name": "Microservices", "skillType": "Capability"},
    "B": {"name": "Docker", "skillType": "Tool"},
    "C": {"name": "Distributed Systems", "skillType": "Knowledge"},
}
EDGES = [
    ("A", "C", "REQUIRES"),
    ("A", "B", "USES"),
]


def _is_domain(skill_id: str) -> bool:
    return closures.make_is_domain(SKILL_META)(skill_id)


def _exp(instance_id: str, *, end: str = "2024-01", company: str = "Acme") -> dict:
    return {
        "instance_id": instance_id,
        "node_label": "ExperienceEvent",
        "company": company,
        "position": "Engineer",
        "start": "2020-01",
        "end": end,
        "skills": [{"id": "A", "name": "Microservices"}],
    }


def _atom(atom_id: str, exp_id: str, skill_id: str, *, strength: float = 1.0) -> dict:
    return {
        "atom_id": atom_id,
        "instance_id": exp_id,
        "kind": "achievement",
        "text": f"Did {skill_id} work.",
        "skill_ids": [skill_id],
        "strength": strength,
        "licensed": [
            {
                "jd_skill_id": skill_id,
                "surface_form": SKILL_META[skill_id]["name"],
                "via": "explicit",
            }
        ],
    }


def test_months_since_end_present_is_zero() -> None:
    assert months_since_end(None, today=date(2026, 1, 1)) == 0.0


def test_allocate_skips_redundant_same_skill_atom() -> None:
    d_star = closures.demand_closure({"A": 1.0}, EDGES, _is_domain)
    demand = {
        "d_star": d_star,
        "weights": {k: 1.0 for k in d_star},
        "edges_subset": EDGES,
    }
    dossier = {"instances": [_exp("exp-1")]}
    atoms = [
        _atom("a1", "exp-1", "A"),
        _atom("a2", "exp-1", "A"),
    ]
    allocation = run_allocation(
        dossier,
        atoms,
        demand,
        {"page_budget": 2, "max_highlights_total": 5},
        {"title": "Microservices Engineer"},
        EDGES,
        _is_domain,
    )
    assert allocation.selected["exp-1"] == ["a1"]


def test_allocate_min_one_line_per_tiered_role() -> None:
    d_star = closures.demand_closure({"A": 1.0, "B": 1.0}, EDGES, _is_domain)
    demand = {
        "d_star": d_star,
        "weights": {k: 1.0 for k in d_star},
        "edges_subset": EDGES,
    }
    dossier = {
        "instances": [
            _exp("exp-a", end="2024-06"),
            _exp("exp-b", end="2023-06", company="Other"),
        ]
    }
    atoms = [
        _atom("a1", "exp-a", "A"),
        _atom("b1", "exp-b", "B"),
    ]
    allocation = run_allocation(
        dossier,
        atoms,
        demand,
        {"page_budget": 2, "max_highlights_total": 10},
        {"title": "Engineer"},
        EDGES,
        _is_domain,
    )
    assert len(allocation.selected["exp-a"]) >= 1
    assert len(allocation.selected["exp-b"]) >= 1


def test_allocate_node_integration(monkeypatch) -> None:
    def _fake_graph():
        nodes = {
            nid: SimpleNamespace(name=meta["name"], skill_type=meta["skillType"])
            for nid, meta in SKILL_META.items()
        }
        edge_objs = [SimpleNamespace(source=s, target=t, type=ty) for s, t, ty in EDGES]
        return SimpleNamespace(nodes=nodes, edges=edge_objs)

    node_mod = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.allocate.node"
    )
    monkeypatch.setattr(node_mod, "get_skills_graph", _fake_graph)

    d_star = closures.demand_closure({"A": 1.0}, EDGES, _is_domain)
    state = {
        "dossier": {"instances": [_exp("exp-1")]},
        "demand": {
            "d_star": d_star,
            "weights": {k: 1.0 for k in d_star},
            "edges_subset": EDGES,
        },
        "atoms": [_atom("a1", "exp-1", "A")],
        "template": {"page_budget": 2},
        "jd_context": {"title": "Architect"},
    }
    out = node_mod.allocate(state, {})
    allocation = Allocation.model_validate(out["allocation"])
    assert allocation.instance_order == ["exp-1"]
    assert allocation.selected["exp-1"] == ["a1"]
    assert allocation.resume_fit > 0.0
    assert allocation.resume_fit_baseline is not None
    assert allocation.resume_fit_normalized is not None
    assert 0.0 <= allocation.resume_fit_normalized <= 1.0

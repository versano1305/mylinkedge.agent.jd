"""Tests for WU-06 license_and_value."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from jd_agent.graphs.resume_generate.constants import LICENSE_TAU
from jd_agent.graphs.resume_generate.nodes.license_and_value.enrich import enrich_atoms
from jd_agent.graphs.resume_generate.nodes.license_and_value.node import (
    license_and_value,
)
from jd_agent.shared import skill_closures as closures
from jd_agent.shared.atom_licensing import partition_demand_skill_terms

SKILL_META = {
    "A": {"name": "Microservices", "skillType": "Capability"},
    "B": {"name": "Docker", "skillType": "Tool"},
    "C": {"name": "Distributed Systems", "skillType": "Knowledge"},
    "D": {"name": "Fintech", "skillType": "Domain"},
}
EDGES = [
    ("A", "C", "REQUIRES"),
    ("A", "B", "USES"),
    ("A", "D", "PART_OF"),
]

SPRING_META = {
    "SB": {"name": "Spring Boot", "skillType": "Capability"},
    "JV": {"name": "Java", "skillType": "Capability"},
}
SPRING_EDGES = [("SB", "JV", "REQUIRES")]

PART_OF_META = {
    "P": {"name": "Prometheus", "skillType": "Tool"},
    "O": {"name": "Observability", "skillType": "Knowledge"},
}
PART_OF_EDGES = [("P", "O", "PART_OF")]


def _is_domain(meta: dict) -> closures.IsDomain:
    return closures.make_is_domain(meta)


def _jd_row(skill_id: str, name: str, **extra: object) -> dict:
    return {
        "skill_id": skill_id,
        "name": name,
        "surface_form": name,
        "skill_type": SKILL_META.get(skill_id, {}).get("skillType", "Capability"),
        "weight": 1.0,
        **extra,
    }


def test_explicit_subset_of_licensed_and_implied_one_hop() -> None:
    d_star = closures.demand_closure({"JV": 1.0}, SPRING_EDGES, _is_domain(SPRING_META))
    s_star = closures.supply_closure_noisy_or(
        {"SB": 1.0}, SPRING_EDGES, _is_domain(SPRING_META)
    )
    licensed, adjacent = partition_demand_skill_terms(
        atom_skill_ids={"SB"},
        s_star_atom=s_star,
        d_star=d_star,
        jd_rows_by_id={"JV": _jd_row("JV", "Java")},
        profile_zones={},
        profile_latent_kind={},
        license_tau=LICENSE_TAU,
    )
    assert any(t["jd_skill_id"] == "JV" and t["via"] == "implied" for t in licensed)
    assert s_star["JV"] >= LICENSE_TAU
    assert not adjacent


def test_part_of_only_does_not_license() -> None:
    d_star = closures.demand_closure({"O": 1.0}, PART_OF_EDGES, _is_domain(PART_OF_META))
    s_star = closures.supply_closure_noisy_or(
        {"P": 1.0}, PART_OF_EDGES, _is_domain(PART_OF_META)
    )
    licensed, _ = partition_demand_skill_terms(
        atom_skill_ids={"P"},
        s_star_atom=s_star,
        d_star=d_star,
        jd_rows_by_id={"O": _jd_row("O", "Observability")},
        profile_zones={},
        profile_latent_kind={},
        license_tau=LICENSE_TAU,
    )
    assert licensed == []
    assert s_star.get("O", 0.0) < LICENSE_TAU


def test_no_licensed_outside_d_star() -> None:
    d_star = {"A": 1.0}
    licensed, _ = partition_demand_skill_terms(
        atom_skill_ids={"A", "Z"},
        s_star_atom={"A": 1.0},
        d_star=d_star,
        jd_rows_by_id={
            "A": _jd_row("A", "Microservices"),
            "Z": _jd_row("Z", "Ghost"),
        },
        profile_zones={},
        profile_latent_kind={},
        license_tau=LICENSE_TAU,
    )
    assert {t["jd_skill_id"] for t in licensed} == {"A"}


def test_profile_latent_marks_adjacent_without_atom_supply() -> None:
    licensed, adjacent = partition_demand_skill_terms(
        atom_skill_ids=set(),
        s_star_atom={},
        d_star={"C": 1.0},
        jd_rows_by_id={"C": _jd_row("C", "Distributed Systems")},
        profile_zones={"C": "latent"},
        profile_latent_kind={"C": "adjacent"},
        license_tau=LICENSE_TAU,
    )
    assert not licensed
    assert len(adjacent) == 1
    assert adjacent[0]["jd_skill_id"] == "C"


def test_enrich_atoms_standalone_value_positive() -> None:
    d_star = closures.demand_closure({"A": 1.0}, EDGES, _is_domain(SKILL_META))
    demand = {
        "d_star": d_star,
        "weights": {k: 1.0 for k in d_star},
        "zones": {},
        "latent_kind": {},
        "edges_subset": EDGES,
    }
    atoms = [
        {
            "atom_id": "a1",
            "instance_id": "exp-1",
            "kind": "achievement",
            "text": "Built microservices.",
            "skill_ids": ["A"],
            "strength": 1.0,
        }
    ]
    out = enrich_atoms(
        atoms,
        dossier={"instances": [{"instance_id": "exp-1", "skills": []}]},
        demand=demand,
        jd_targets=[_jd_row("A", "Microservices")],
        jd_domains=[],
        edges_subset=EDGES,
        is_domain=_is_domain(SKILL_META),
    )
    assert out[0]["standalone_value"] > 0
    assert any(t["via"] == "explicit" for t in out[0]["licensed"])


def test_license_and_value_node(monkeypatch) -> None:
    def _fake_graph():
        nodes = {
            nid: SimpleNamespace(name=meta["name"], skill_type=meta["skillType"])
            for nid, meta in SKILL_META.items()
        }
        edge_objs = [SimpleNamespace(source=s, target=t, type=ty) for s, t, ty in EDGES]
        return SimpleNamespace(nodes=nodes, edges=edge_objs)

    node_mod = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.license_and_value.node"
    )
    monkeypatch.setattr(node_mod, "get_skills_graph", _fake_graph)

    d_star = closures.demand_closure({"A": 1.0}, EDGES, _is_domain(SKILL_META))
    state = {
        "atoms": [
            {
                "atom_id": "a1",
                "instance_id": "exp-1",
                "kind": "achievement",
                "text": "Shipped.",
                "skill_ids": ["A"],
                "strength": 0.8,
            }
        ],
        "demand": {
            "d_star": d_star,
            "weights": {k: 1.0 for k in d_star},
            "zones": {},
            "latent_kind": {},
            "edges_subset": EDGES,
        },
        "dossier": {"instances": []},
        "jd_targets": [_jd_row("A", "Microservices")],
        "jd_domains": [],
    }
    result = license_and_value(state, {})
    assert len(result["atoms"]) == 1
    assert result["atoms"][0]["licensed"]

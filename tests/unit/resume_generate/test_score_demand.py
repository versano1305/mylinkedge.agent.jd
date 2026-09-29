"""Unit tests for WU-04 demand scoring."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from jd_agent.graphs.resume_generate.constants import HAS_SKILL_SEED
from jd_agent.graphs.resume_generate.nodes.score_demand.node import score_demand
from jd_agent.graphs.resume_generate.nodes.score_demand.profile_seeds import (
    profile_supply_seeds,
)
from jd_agent.shared.skill_closures import supply_closure_noisy_or
from jd_agent.shared.supply_edge_prune import prune_supply_edges

SKILL_META = {
    "A": {"name": "Microservices", "skillType": "Capability"},
    "B": {"name": "Docker", "skillType": "Tool"},
    "C": {"name": "Distributed Systems", "skillType": "Knowledge"},
}
EDGES = [
    ("A", "C", "REQUIRES"),
    ("A", "B", "USES"),
]


def test_profile_supply_seeds_splits_instance_and_has_skill() -> None:
    dossier = {
        "instances": [{"skills": [{"id": "B", "name": "Docker"}]}],
        "skills": [{"id": "B"}, {"id": "X", "name": "ProfileOnly"}],
    }
    s_seed, s_explicit = profile_supply_seeds(dossier, has_skill_seed=HAS_SKILL_SEED)
    assert s_seed["B"] == 1.0
    assert s_explicit["B"] == 1.0
    assert s_seed["X"] == pytest.approx(HAS_SKILL_SEED)
    assert s_explicit.get("X", 0.0) == 0.0


def test_score_demand_node_builds_demand_payload(monkeypatch) -> None:
    def _fake_graph():
        nodes = {
            nid: SimpleNamespace(name=meta["name"], skill_type=meta["skillType"])
            for nid, meta in SKILL_META.items()
        }
        edge_objs = [SimpleNamespace(source=s, target=t, type=ty) for s, t, ty in EDGES]
        return SimpleNamespace(nodes=nodes, edges=edge_objs)

    node_mod = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.score_demand.node"
    )
    monkeypatch.setattr(node_mod, "get_skills_graph", _fake_graph)

    state = {
        "jd_targets": [
            {
                "skill_id": "A",
                "name": "Microservices",
                "weight": 1.0,
                "importance": 1.0,
            }
        ],
        "dossier": {
            "user_id": "owner-1",
            "instances": [{"skills": [{"id": "B"}]}],
            "skills": [],
        },
    }
    out = score_demand(state, {})
    demand = out["demand"]

    assert demand["fit_profile"] >= 0.0
    assert "A" in demand["d_star"]
    assert demand["zones"]["B"] == "confirmed"
    assert demand["listed_jd_skill_ids"] == ["A"]
    assert demand["edges_subset"]

    is_domain = lambda sid: False  # noqa: E731
    full = supply_closure_noisy_or({"B": 1.0}, EDGES, is_domain)
    pruned = supply_closure_noisy_or({"B": 1.0}, demand["edges_subset"], is_domain)
    for sid in demand["d_star"]:
        assert pruned.get(sid, 0.0) == pytest.approx(full.get(sid, 0.0))


def test_score_demand_requires_jd_targets() -> None:
    with pytest.raises(ValueError, match="jd_targets"):
        score_demand({"dossier": {"user_id": "x"}}, {})

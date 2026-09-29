"""Tests for supply-edge pruning used by resume demand scoring."""

from __future__ import annotations

import pytest

from jd_agent.shared.skill_closures import (
    demand_closure,
    make_is_domain,
    supply_closure_noisy_or,
)
from jd_agent.shared.supply_edge_prune import prune_supply_edges

SKILL_META = {
    "A": {"name": "Microservices", "skillType": "Capability"},
    "B": {"name": "Docker", "skillType": "Tool"},
    "C": {"name": "Distributed Systems", "skillType": "Knowledge"},
    "D": {"name": "Fintech", "skillType": "Domain"},
    "E": {"name": "Far", "skillType": "Tool"},
}
EDGES = [
    ("A", "C", "REQUIRES"),
    ("A", "B", "USES"),
    ("A", "D", "PART_OF"),
    ("E", "E", "USES"),  # self-loop noise; far from demand when E isolated
]
# Long chain: demand at F, supply seed at H — pruning should keep the chain.
CHAIN_EDGES = [
    ("F", "G", "USES"),
    ("G", "H", "ENABLES"),
    ("H", "I", "PART_OF"),
    ("X", "Y", "USES"),
]
CHAIN_META = {
    "F": {"name": "F", "skillType": "Capability"},
    "G": {"name": "G", "skillType": "Tool"},
    "H": {"name": "H", "skillType": "Tool"},
    "I": {"name": "I", "skillType": "Knowledge"},
    "X": {"name": "X", "skillType": "Tool"},
    "Y": {"name": "Y", "skillType": "Tool"},
}


def _is_domain(meta: dict[str, dict[str, str]]):
    return make_is_domain(meta)


def test_prune_supply_edges_matches_full_closure_on_d_star() -> None:
    is_domain = _is_domain(SKILL_META)
    d_star = demand_closure({"A": 1.0}, EDGES, is_domain)
    seeds = {"B": 1.0}
    full = supply_closure_noisy_or(seeds, EDGES, is_domain)
    subset_edges = prune_supply_edges(EDGES, d_star, is_domain)
    assert len(subset_edges) <= len(EDGES)
    pruned = supply_closure_noisy_or(seeds, subset_edges, is_domain)
    for sid, dv in d_star.items():
        if dv <= 0:
            continue
        assert pruned.get(sid, 0.0) == pytest.approx(full.get(sid, 0.0))


def test_prune_supply_edges_drops_unreachable_ontology_edges() -> None:
    is_domain = _is_domain(SKILL_META)
    d_star = demand_closure({"A": 1.0}, EDGES, is_domain)
    subset = prune_supply_edges(EDGES, d_star, is_domain)
    assert ("E", "E", "USES") not in subset


def test_prune_supply_edges_preserves_long_upstream_chain() -> None:
    is_domain = _is_domain(CHAIN_META)
    d_star = demand_closure({"F": 1.0}, CHAIN_EDGES, is_domain)
    seeds = {"I": 1.0}
    full = supply_closure_noisy_or(seeds, CHAIN_EDGES, is_domain)
    subset = prune_supply_edges(CHAIN_EDGES, d_star, is_domain)
    assert ("X", "Y", "USES") not in subset
    pruned = supply_closure_noisy_or(seeds, subset, is_domain)
    for sid in d_star:
        assert pruned.get(sid, 0.0) == pytest.approx(full.get(sid, 0.0))

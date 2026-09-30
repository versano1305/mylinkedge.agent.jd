"""Unit tests for gap closures, zones, ranking, and the compute node."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from jd_agent.shared import gap_zones as zones
from jd_agent.shared import skill_closures as closures
from jd_agent.graphs.gap_collect.nodes.compute_gaps.node import compute_gaps_node
from jd_agent.graphs.gap_collect.nodes.rank_queue.ranking import (
    p_has,
    rank_candidates,
)

# A → C (REQUIRES), A → B (USES), A → D (PART_OF, D is a Domain and masked).
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


def _is_domain():
    return closures.make_is_domain(SKILL_META)


def test_demand_closure_propagates_to_prerequisites() -> None:
    d_star = closures.demand_closure({"A": 1.0}, EDGES, _is_domain())
    assert d_star["A"] == pytest.approx(1.0)
    assert d_star["C"] == pytest.approx(closures.DEMAND_GAMMA)  # REQUIRES
    assert d_star["B"] == pytest.approx(closures.DEMAND_GAMMA)  # USES
    assert "D" not in d_star  # Domain masked


def test_supply_closure_lifts_related_skills() -> None:
    s_star = closures.supply_closure_noisy_or({"B": 1.0}, EDGES, _is_domain())
    assert s_star["B"] == pytest.approx(1.0)
    assert s_star.get("A", 0.0) > 0.0  # USES backward lifts A a little
    assert "D" not in s_star  # Domain masked


def test_compute_gaps_fit_perfect_when_supply_covers_demand() -> None:
    d_star = {"A": 1.0}
    s_star = {"A": 1.0}
    gaps, fit = zones.compute_gaps(d_star, s_star, {"A": 1.0})
    assert gaps["A"] == pytest.approx(0.0)
    assert fit == pytest.approx(1.0)


def test_fit_if_latent_skills_confirmed_raises_fit() -> None:
    """Confirming a latent seed should not lower fit vs baseline."""
    d_star = closures.demand_closure({"A": 1.0}, EDGES, _is_domain())
    s_seed = {"B": 1.0}
    s_star = closures.supply_closure_noisy_or(s_seed, EDGES, _is_domain())
    weights = {sid: 1.0 for sid in d_star}
    _, fit_before = zones.compute_gaps(d_star, s_star, weights)
    # C is demanded via A but not seeded — treat as latent to confirm.
    fit_after = zones.fit_if_latent_skills_confirmed(
        d_star, s_seed, {"C"}, EDGES, _is_domain(), weights
    )
    assert fit_after >= fit_before


def test_assign_zone_partitions() -> None:
    s_explicit = {"confirmed": 1.0}
    s_star = {"implied": 0.6, "confirmed": 1.0}
    ppr = {"adjacent": 0.02}
    rho = 0.01

    assert zones.assign_zone("confirmed", s_explicit, s_star, ppr, rho)[0] == "confirmed"
    zone, kind = zones.assign_zone("implied", s_explicit, s_star, ppr, rho)
    assert (zone, kind) == ("latent", "implied")
    zone, kind = zones.assign_zone("adjacent", s_explicit, s_star, ppr, rho)
    assert (zone, kind) == ("latent", "adjacent")
    assert zones.assign_zone("nowhere", s_explicit, s_star, ppr, rho)[0] == "true_gap"


def test_assign_zone_discounts_supply_any_profile_gets() -> None:
    s_star = {"implied": 0.6}
    assert zones.assign_zone("implied", {}, s_star, {}, 1.0)[0] == "latent"
    # Random profiles already reach 0.5 here, so 0.6 is only 20% above chance.
    zone = zones.assign_zone(
        "implied", {}, s_star, {}, 1.0, s_star_baseline={"implied": 0.5}
    )[0]
    assert zone == "true_gap"


def test_p_has_monotonic_in_supply() -> None:
    assert p_has(0.9, 0.0) > p_has(0.1, 0.0)


def test_rank_candidates_orders_by_expected_yield_and_bundles() -> None:
    candidates = [
        {
            "skill_id": "low",
            "skill_name": "Low",
            "skill_type": "Tool",
            "zone": "true_gap",
            "s_star": 0.0,
            "ppr": 0.0,
            "gap": 0.9,
            "weight": 1.0,
            "theme_id": "theme-1",
        },
        {
            "skill_id": "high",
            "skill_name": "High",
            "skill_type": "Tool",
            "zone": "latent",
            "s_star": 0.9,
            "ppr": 0.01,
            "gap": 0.3,
            "weight": 1.0,
            "theme_id": "theme-1",
        },
    ]
    result = rank_candidates(candidates)
    queue = result["queue"]
    # The latent, likely-held skill outranks the big true-gap despite smaller gap.
    assert queue[0]["skill_id"] == "high"
    assert queue[0]["round_id"] == "skill::high"
    assert result["bundles"] == [
        {"theme_id": "theme-1", "round_ids": ["skill::high", "skill::low"]}
    ]
    assert result["stopping"]["target_questions"] > 0


def _fake_graph():
    nodes = {
        nid: SimpleNamespace(name=meta["name"], skill_type=meta["skillType"])
        for nid, meta in SKILL_META.items()
    }
    edges = [SimpleNamespace(source=s, target=t, type=ty) for s, t, ty in EDGES]
    return SimpleNamespace(nodes=nodes, edges=edges)


def test_compute_gaps_node_builds_full_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "jd_agent.graphs.gap_collect.nodes.compute_gaps.node.get_skills_graph",
        _fake_graph,
    )
    state = {
        "jd_raw_skills": [{"id": "A", "name": "Microservices", "requirement_level": 0.4}],
        "user_skill_ids": ["B"],
        "evidence_skill_ids": ["B"],
    }
    out = compute_gaps_node(state, {})

    gaps = out["gaps"]
    assert gaps["schema_version"] == 1
    assert set(gaps.keys()) >= {"meta", "review", "skills"}
    assert gaps["meta"]["resolved_count"] == 1
    assert "fit_if_all_latent" in gaps["meta"]
    assert "fit_uplift_latent" in gaps["meta"]
    assert gaps["meta"]["fit_if_all_latent"] >= gaps["meta"]["fit"]
    meta = gaps["meta"]
    assert 0.0 <= meta["fit_baseline"] <= 1.0
    assert 0.0 <= meta["fit_normalized"] <= 1.0
    assert meta["fit_if_all_latent_normalized"] >= meta["fit_normalized"]
    assert meta["fit_explicit"] <= meta["fit"]
    assert meta["ontology"]["edge_count"] == len(EDGES)
    assert gaps["review"]["headline"].startswith(f"{round(meta['fit_normalized'] * 100)}% fit")
    assert all("s_star_baseline" in row for row in gaps["skills"])

    zones_seen = {row["skill_id"]: row["zone"] for row in gaps["skills"]}
    by_id = {row["skill_id"]: row for row in gaps["skills"]}
    assert by_id["A"]["requirement_level"] == 0.4
    assert isinstance(by_id["A"]["requirement_level"], float)
    assert by_id["B"]["requirement_level"] == 1.0
    assert by_id["C"]["requirement_level"] == 1.0
    assert zones_seen["B"] == "confirmed"  # evidence-backed
    # A and C are demanded but unmet → interview candidates exist.
    assert out["interview_candidates"]
    assert all("expected_yield" not in c for c in out["interview_candidates"])

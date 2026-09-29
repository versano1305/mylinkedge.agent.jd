"""Tests for ontology-density damping and chance-corrected fit."""

from __future__ import annotations

import pytest

from jd_agent.shared import skill_closures as sc
from jd_agent.shared.fit_baseline import (
    DegreeMatchedSampler,
    chance_corrected_fit,
    explicit_fit,
    ontology_fingerprint,
    profile_baseline,
)
from jd_agent.shared.gap_zones import compute_gaps

JD = [f"J{i}" for i in range(10)]
POOL = [f"P{i}" for i in range(100)]
NOISE = [f"Z{i}" for i in range(200)]
CATEGORIES = [f"C{i}" for i in range(5)]
META = {sid: {"name": sid, "skillType": "Tool"} for sid in JD + POOL + NOISE + CATEGORIES}
BEFORE = [(p, CATEGORIES[i % 5], "PART_OF") for i, p in enumerate(POOL)]
# The expansion connects every pool skill to every JD skill.
AFTER = BEFORE + [(p, j, "ENABLES") for p in POOL for j in JD]
D_STAR = {j: 1.0 for j in JD}
WEIGHTS = {j: 1.0 for j in JD}


def _is_domain(_sid: str) -> bool:
    return False


def _fits(edges, seeds):
    fanout = sc.supply_fanout(edges, _is_domain)
    s_star = sc.supply_closure_noisy_or(seeds, edges, _is_domain, fanout=fanout)
    fit = compute_gaps(D_STAR, s_star, WEIGHTS)[1]
    baseline = profile_baseline(
        D_STAR,
        WEIGHTS,
        seeds,
        edges,
        _is_domain,
        DegreeMatchedSampler(edges, META),
        fanout=fanout,
    )
    return fit, chance_corrected_fit(fit, baseline.mean)


def test_fanout_scale_only_damps_hubs() -> None:
    assert sc.fanout_scale(1) == 1.0
    assert sc.fanout_scale(sc.SUPPLY_FANOUT_REF) == 1.0
    assert sc.fanout_scale(sc.SUPPLY_FANOUT_REF * 4) == pytest.approx(
        0.25**sc.SUPPLY_FANOUT_BETA
    )


def test_hub_passes_less_supply_to_each_target() -> None:
    small = [("H", f"T{i}", "REQUIRES") for i in range(2)]
    hub = [("H", f"T{i}", "REQUIRES") for i in range(sc.SUPPLY_FANOUT_REF * 10)]
    s_small = sc.supply_closure_noisy_or({"H": 1.0}, small, _is_domain)
    s_hub = sc.supply_closure_noisy_or({"H": 1.0}, hub, _is_domain)
    assert s_small["T0"] == pytest.approx(sc.ALPHA[("REQUIRES", "fwd")])
    assert s_hub["T0"] < s_small["T0"]


def test_top_k_caps_parallel_paths() -> None:
    edges = [(f"S{i}", "T", "ENABLES") for i in range(10)]
    seeds = {f"S{i}": 1.0 for i in range(10)}
    alpha = sc.ALPHA[("ENABLES", "fwd")]
    capped = sc.supply_closure_noisy_or(seeds, edges, _is_domain)
    uncapped = sc.supply_closure_noisy_or(seeds, edges, _is_domain, top_k=None)
    assert capped["T"] == pytest.approx(1 - (1 - alpha) ** sc.SUPPLY_TOP_K)
    assert uncapped["T"] > capped["T"]


def test_chance_corrected_fit() -> None:
    assert chance_corrected_fit(0.5, 0.0) == pytest.approx(0.5)
    assert chance_corrected_fit(0.95, 0.9) == pytest.approx(0.5)
    assert chance_corrected_fit(0.8, 0.9) == 0.0
    assert chance_corrected_fit(1.0, 1.0) == 0.0


def test_baseline_is_deterministic() -> None:
    seeds = {p: 1.0 for p in POOL[:10]}
    assert _fits(AFTER, seeds) == _fits(AFTER, seeds)


def test_expansion_inflates_raw_fit_but_not_normalized_fit() -> None:
    seeds = {p: 1.0 for p in POOL[:10]}
    fit_before, norm_before = _fits(BEFORE, seeds)
    fit_after, norm_after = _fits(AFTER, seeds)
    assert fit_after - fit_before > 0.5
    assert norm_before == pytest.approx(0.0, abs=0.05)
    assert norm_after == pytest.approx(0.0, abs=0.05)


def test_matching_profile_beats_chance() -> None:
    matched = {**{j: 1.0 for j in JD[:5]}, **{p: 1.0 for p in POOL[:5]}}
    chance = {p: 1.0 for p in POOL[:10]}
    _, norm_matched = _fits(BEFORE, matched)
    _, norm_chance = _fits(BEFORE, chance)
    assert norm_matched > 0.4
    assert norm_matched > norm_chance


def test_explicit_fit_ignores_propagation() -> None:
    seeds = {p: 1.0 for p in POOL[:10]}
    assert explicit_fit(D_STAR, WEIGHTS, seeds) == 0.0
    assert explicit_fit(D_STAR, WEIGHTS, {"J0": 1.0}) == pytest.approx(0.1)


def test_ontology_fingerprint_changes_with_edges() -> None:
    before = ontology_fingerprint(BEFORE)
    after = ontology_fingerprint(AFTER)
    assert before["edge_count"] == len(BEFORE)
    assert before["edge_hash"] != after["edge_hash"]
    assert before == ontology_fingerprint(list(reversed(BEFORE)))

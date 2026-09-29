"""Tests for resume-level fit helpers."""

from __future__ import annotations

import pytest

from jd_agent.shared import skill_closures as closures
from jd_agent.shared.resume_fit import delta_fit, merge_supply_seeds, resume_fit

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


def test_merge_supply_seeds_keeps_max() -> None:
    merged = merge_supply_seeds({"A": 0.5}, {"A": 1.0, "B": 0.8})
    assert merged == {"A": 1.0, "B": 0.8}


def test_second_atom_same_skill_has_low_marginal_gain() -> None:
    d_star = closures.demand_closure({"A": 1.0}, EDGES, _is_domain)
    weights = {k: 1.0 for k in d_star}
    first = {"A": 1.0}
    second = delta_fit(first, {"A": 1.0}, d_star, weights, EDGES, _is_domain)
    assert second == pytest.approx(0.0, abs=1e-6)


def test_resume_fit_empty_seeds_is_below_full_proof() -> None:
    d_star = closures.demand_closure({"A": 1.0}, EDGES, _is_domain)
    weights = {k: 1.0 for k in d_star}
    empty = resume_fit(d_star, weights, {}, EDGES, _is_domain)
    full = resume_fit(d_star, weights, {"A": 1.0}, EDGES, _is_domain)
    assert empty < full

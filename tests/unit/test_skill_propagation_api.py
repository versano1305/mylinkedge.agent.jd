"""Contract tests for ``skill_propagation_api``."""

from __future__ import annotations

from jd_agent.shared.skill_closures import (
    demand_closure,
    supply_closure_noisy_or,
    supply_fanout,
)
from jd_agent.shared.skill_propagation_api import (
    DemandPropagationRequest,
    PprPropagationRequest,
    SkillGraphContext,
    SupplyPropagationRequest,
    compute_demand,
    compute_ppr,
    compute_supply,
)

EDGES: list[tuple[str, str, str]] = [
    ("A", "B", "REQUIRES"),
    ("B", "C", "USES"),
    ("H", "A", "PART_OF"),
]

META = {
    "A": {"name": "A", "skillType": "Tool"},
    "B": {"name": "B", "skillType": "Tool"},
    "C": {"name": "C", "skillType": "Tool"},
    "H": {"name": "H", "skillType": "Knowledge"},
    "D": {"name": "D", "skillType": "Domain"},
}


def _is_domain(sid: str) -> bool:
    return META.get(sid, {}).get("skillType") == "Domain"


def test_compute_demand_matches_closure() -> None:
    ctx = SkillGraphContext.from_parts(EDGES, _is_domain)
    req = DemandPropagationRequest(context=ctx, seeds={"A": 1.0})
    out = compute_demand(req)
    expected = demand_closure({"A": 1.0}, EDGES, _is_domain)
    assert out.d_star == {k: v for k, v in expected.items() if v > 0}
    assert out.seeds == frozenset({"A"})


def test_compute_supply_pruned_edges_with_full_fanout() -> None:
    is_domain = _is_domain
    fanout = supply_fanout(EDGES, is_domain)
    ctx = SkillGraphContext.from_parts(EDGES, is_domain, fanout=fanout)
    subset = [e for e in EDGES if e[0] != "H"]
    req = SupplyPropagationRequest(
        context=ctx,
        seeds={"B": 1.0},
        propagation_edges=tuple(subset),
    )
    out = compute_supply(req)
    full = supply_closure_noisy_or(
        {"B": 1.0}, EDGES, is_domain, fanout=fanout
    )
    assert out.s_star.get("C", 0.0) == full.get("C", 0.0)


def test_compute_ppr_returns_scope_and_rho() -> None:
    ctx = SkillGraphContext.from_parts(EDGES, _is_domain)
    d = compute_demand(
        DemandPropagationRequest(context=ctx, seeds={"A": 1.0})
    )
    scope = frozenset(d.d_star)
    out = compute_ppr(
        PprPropagationRequest(
            context=ctx,
            demand_scope=scope,
            ppr_seed_ids=frozenset({"B"}),
        )
    )
    assert scope <= set(out.scores)
    assert out.rho >= 0.0

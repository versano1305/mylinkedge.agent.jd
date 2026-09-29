"""Backward-compatible re-exports; canonical code lives in ``jd_agent.shared``."""

from jd_agent.shared.skill_closures import (  # noqa: F401
    ALPHA,
    DEMAND_GAMMA,
    DOMAIN_SKILL_TYPE,
    SUPPLY_HOPS,
    Edge,
    IsDomain,
    SupplyInfluence,
    build_supply_influence,
    demand_closure,
    make_is_domain,
    scc_warn,
    supply_closure_noisy_or,
)

__all__ = [
    "ALPHA",
    "DEMAND_GAMMA",
    "DOMAIN_SKILL_TYPE",
    "SUPPLY_HOPS",
    "Edge",
    "IsDomain",
    "SupplyInfluence",
    "build_supply_influence",
    "demand_closure",
    "make_is_domain",
    "scc_warn",
    "supply_closure_noisy_or",
]

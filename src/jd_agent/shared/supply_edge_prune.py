"""Prune the global Skill graph to the supply neighborhood of JD demand."""

from __future__ import annotations

from collections import defaultdict

from jd_agent.shared.skill_closures import (
    SUPPLY_HOPS,
    Edge,
    IsDomain,
    build_supply_influence,
)


def upstream_supply_nodes(
    d_star: dict[str, float],
    influence: list[tuple[str, str, float]],
    *,
    hops: int = SUPPLY_HOPS,
) -> set[str]:
    """Skill ids within ``hops`` reverse-influence steps of positive demand."""

    demand_nodes = {n for n, d in d_star.items() if d > 0}
    if not demand_nodes:
        return set()

    upstream: dict[str, list[str]] = defaultdict(list)
    for src, tgt, _alpha in influence:
        upstream[tgt].append(src)

    allowed = set(demand_nodes)
    frontier = set(demand_nodes)
    for _ in range(hops):
        nxt: set[str] = set()
        for node in frontier:
            for pred in upstream.get(node, []):
                if pred not in allowed:
                    allowed.add(pred)
                    nxt.add(pred)
        frontier = nxt
        if not frontier:
            break
    return allowed


def prune_supply_edges(
    edges: list[Edge],
    d_star: dict[str, float],
    is_domain: IsDomain,
    hops: int = SUPPLY_HOPS,
) -> list[Edge]:
    """Return ontology edges that can affect supply on the demand closure.

    Keeps edges whose endpoints both lie within ``SUPPLY_HOPS`` reverse-influence
    hops of some ``d_star`` node (Domain endpoints excluded, matching closures).
    """

    influence = build_supply_influence(edges, is_domain)
    allowed = upstream_supply_nodes(d_star, influence, hops=hops)
    if not allowed:
        return []

    return [
        (u, v, r)
        for u, v, r in edges
        if not is_domain(u) and not is_domain(v) and u in allowed and v in allowed
    ]

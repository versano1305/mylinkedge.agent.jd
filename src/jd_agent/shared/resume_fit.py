"""Resume-level fit from evidence seeds (WU-06 / WU-07).

Uses the same supply closure and ``compute_gaps`` aggregate as gap scoring,
but seeded from selected resume atoms rather than the full profile.
"""

from __future__ import annotations

from jd_agent.shared.gap_zones import compute_gaps
from jd_agent.shared.skill_closures import IsDomain, Edge, supply_closure_noisy_or


def merge_supply_seeds(*parts: dict[str, float]) -> dict[str, float]:
    """Combine seed maps; per skill id keep the maximum seed weight."""

    merged: dict[str, float] = {}
    for part in parts:
        for sid, weight in part.items():
            w = float(weight)
            if w <= 0:
                continue
            merged[sid] = max(merged.get(sid, 0.0), w)
    return merged


def supply_star(
    seeds: dict[str, float],
    edges: list[Edge],
    is_domain: IsDomain,
) -> dict[str, float]:
    """Supply closure over ``edges`` (typically ``demand[\"edges_subset\"]``)."""

    if not seeds:
        return {}
    return supply_closure_noisy_or(seeds, edges, is_domain)


def resume_fit(
    d_star: dict[str, float],
    weights: dict[str, float],
    seeds: dict[str, float],
    edges: list[Edge],
    is_domain: IsDomain,
) -> float:
    """Aggregate JD fit for a resume seeded with ``seeds``."""

    if not d_star:
        return 1.0
    s_star = supply_star(seeds, edges, is_domain)
    _, fit = compute_gaps(d_star, s_star, weights)
    return float(fit)


def delta_fit(
    current_seeds: dict[str, float],
    add_seeds: dict[str, float],
    d_star: dict[str, float],
    weights: dict[str, float],
    edges: list[Edge],
    is_domain: IsDomain,
) -> float:
    """Marginal fit gain from unioning ``add_seeds`` into ``current_seeds``."""

    before = resume_fit(d_star, weights, current_seeds, edges, is_domain)
    after = resume_fit(
        d_star, weights, merge_supply_seeds(current_seeds, add_seeds), edges, is_domain
    )
    return after - before

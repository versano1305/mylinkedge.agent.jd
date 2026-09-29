"""Gap scoring, the three-zone partition, themes, and the critical path.

Ported from ``notebooks/jd_gap_collector_v2``. The three-zone partition
(Confirmed / Latent / True gap) replaces flat gap scoring for candidate-facing
products: absence in a resume is weak evidence of absence in a person, so the
Latent zone (the graph credits it, the document didn't state it) is where the
interview earns its value.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

import networkx as nx
from networkx.algorithms.community import louvain_communities

from jd_agent.shared.skill_closures import (
    Edge,
    IsDomain,
    supply_closure_noisy_or,
)

# Zone thresholds.
LATENT_DELTA = 0.35  # s* above this ⇒ structurally implied (high prior).
PPR_PERCENTILE = 70  # ρ = this percentile of PPR over the demand closure.
GAP_P = 1  # 1 = linear deficit; 2 punishes large deficits.
DEFAULT_WEIGHT = 1.0  # must-have; Supabase JD skills carry no preferred flag yet.

# Zone identifiers used throughout the stored jsonb.
ZONE_CONFIRMED = "confirmed"
ZONE_LATENT = "latent"
ZONE_TRUE_GAP = "true_gap"

SkillMeta = dict[str, dict[str, str]]


def compute_gaps(
    d_star: dict[str, float],
    s_star: dict[str, float],
    weights: dict[str, float],
    p: int = GAP_P,
) -> tuple[dict[str, float], float]:
    """Return per-node gaps and the aggregate Fit score."""
    gaps: dict[str, float] = {}
    num = 0.0
    den = 0.0
    for v, dv in d_star.items():
        if dv <= 0:
            continue
        w = weights.get(v, DEFAULT_WEIGHT)
        sv = s_star.get(v, 0.0)
        gap = w * dv * (max(0.0, dv - sv) ** p)
        gaps[v] = gap
        num += gap
        den += w * (dv**2)
    fit = 1.0 - (num / den) if den > 0 else 1.0
    return gaps, fit


def fit_if_latent_skills_confirmed(
    d_star: dict[str, float],
    s_seed: dict[str, float],
    latent_ids: set[str],
    edges: list[Edge],
    is_domain: IsDomain,
    weights: dict[str, float],
) -> float:
    """Counterfactual fit if every latent skill were confirmed at full mastery.

    Re-runs supply closure with latent node ids added to the evidence seeds at
    ``1.0``, then recomputes aggregate fit (includes propagation to neighbors).
    """
    if not latent_ids:
        _, fit = compute_gaps(
            d_star, supply_closure_noisy_or(s_seed, edges, is_domain), weights
        )
        return fit
    augmented = dict(s_seed)
    for sid in latent_ids:
        augmented[sid] = 1.0
    s_star_aug = supply_closure_noisy_or(augmented, edges, is_domain)
    _, fit = compute_gaps(d_star, s_star_aug, weights)
    return fit


def personalized_pagerank(
    edges: list[Edge],
    d_star: dict[str, float],
    held_ids: set[str],
    is_domain: IsDomain,
    *,
    alpha: float = 0.85,
    percentile: int = PPR_PERCENTILE,
) -> tuple[dict[str, float], float]:
    """PPR seeded on held skills over the demand-closure neighborhood.

    Returns ``(ppr, rho)`` where ``rho`` is the percentile threshold used to
    flag "adjacent" latent skills.
    """
    demand_nodes = set(d_star)
    ppr_graph = nx.Graph()
    for u, v, _r in edges:
        if (u in demand_nodes or v in demand_nodes) and not (
            is_domain(u) or is_domain(v)
        ):
            ppr_graph.add_edge(u, v)
    for n in demand_nodes:
        ppr_graph.add_node(n)

    if ppr_graph.number_of_nodes() == 0:
        return {n: 0.0 for n in demand_nodes}, 0.0

    personalization = {n: 0.0 for n in ppr_graph.nodes()}
    seed_mass = [sid for sid in held_ids if sid in ppr_graph]
    if seed_mass:
        mass = 1.0 / len(seed_mass)
        for sid in seed_mass:
            personalization[sid] = mass
    else:
        mass = 1.0 / ppr_graph.number_of_nodes()
        personalization = {n: mass for n in ppr_graph.nodes()}

    try:
        ppr = nx.pagerank(ppr_graph, personalization=personalization, alpha=alpha)
    except (nx.PowerIterationFailedConvergence, ZeroDivisionError):
        ppr = {n: 0.0 for n in demand_nodes}

    on_demand = [ppr.get(n, 0.0) for n in demand_nodes]
    rho = _quantile(on_demand, percentile / 100.0) if on_demand else 0.0
    return ppr, rho


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    quantiles = statistics.quantiles(values, n=100, method="inclusive")
    idx = min(max(int(round(q * 100)) - 1, 0), len(quantiles) - 1)
    return float(quantiles[idx])


def assign_zone(
    skill_id: str,
    s_explicit: dict[str, float],
    s_star: dict[str, float],
    ppr: dict[str, float],
    rho: float,
) -> tuple[str, str]:
    """Return ``(zone, latent_kind)``; latent_kind ∈ {'', 'implied', 'adjacent'}."""
    s_v = s_explicit.get(skill_id, 0.0)
    s_star_v = s_star.get(skill_id, 0.0)
    ppr_v = ppr.get(skill_id, 0.0)
    if s_v > 0:
        return ZONE_CONFIRMED, ""
    if s_star_v > LATENT_DELTA or ppr_v > rho:
        kind = "implied" if s_star_v > LATENT_DELTA else "adjacent"
        return ZONE_LATENT, kind
    return ZONE_TRUE_GAP, ""


def build_themes(
    edges: list[Edge],
    unmet_ids: set[str],
    zone_of: dict[str, str],
    skill_meta: SkillMeta,
    *,
    resolution: float = 1.0,
    seed: int = 42,
) -> list[dict[str, object]]:
    """Louvain communities over the unmet (Latent + True gap) subgraph.

    Each theme carries a human label plus a stacked Confirmed/Latent/True-gap
    bar so the review UI never has to render the graph itself.
    """
    theme_graph = nx.Graph()
    for u, v, _r in edges:
        if u in unmet_ids and v in unmet_ids:
            theme_graph.add_edge(u, v)
    for sid in unmet_ids:
        theme_graph.add_node(sid)

    if theme_graph.number_of_nodes() == 0:
        return []

    communities = louvain_communities(
        theme_graph, seed=seed, resolution=resolution
    )
    themes: list[dict[str, object]] = []
    for i, comm in enumerate(sorted(communities, key=len, reverse=True), start=1):
        members = sorted(comm)
        label = skill_group_label(members, edges, skill_meta)
        bars = {ZONE_CONFIRMED: 0, ZONE_LATENT: 0, ZONE_TRUE_GAP: 0}
        for m in members:
            bars[zone_of.get(m, ZONE_TRUE_GAP)] += 1
        themes.append(
            {
                "id": f"theme-{i}",
                "label": label,
                "size": len(members),
                "bars": bars,
                "skill_ids": members,
            }
        )
    return themes


def skill_group_label(
    members: list[str],
    edges: list[Edge],
    skill_meta: SkillMeta,
) -> str:
    """Human label for a set of related skills (PART_OF parent when possible)."""

    comm = set(members)
    return _theme_label(sorted(members), comm, edges, skill_meta)


def _theme_label(
    members: list[str],
    comm: set[str],
    edges: list[Edge],
    skill_meta: SkillMeta,
) -> str:
    parent_counts: dict[str, int] = defaultdict(int)
    for u, v, r in edges:
        if r == "PART_OF" and u in comm:
            parent_counts[skill_meta.get(v, {}).get("name") or v] += 1
    if parent_counts:
        return max(parent_counts, key=lambda k: parent_counts[k])
    knowledge = [
        skill_meta.get(m, {}).get("name") or m
        for m in members
        if skill_meta.get(m, {}).get("skillType") == "Knowledge"
    ]
    if knowledge:
        return knowledge[0]
    return skill_meta.get(members[0], {}).get("name") or members[0]


def critical_path(
    edges: list[Edge],
    true_gap_ids: set[str],
    skill_meta: SkillMeta,
) -> str:
    """Longest ``REQUIRES`` chain among True-gap nodes, as one sentence."""
    req_g = nx.DiGraph()
    for u, v, r in edges:
        if r == "REQUIRES" and u in true_gap_ids and v in true_gap_ids:
            req_g.add_edge(u, v)

    if req_g.number_of_edges() == 0:
        return "No multi-skill foundational chain among true gaps."

    try:
        path = nx.dag_longest_path(req_g)
    except nx.NetworkXUnfeasible:
        return "REQUIRES subgraph has a cycle; critical path skipped."

    names = [skill_meta.get(n, {}).get("name") or n for n in path]
    if len(names) < 2:
        return "No multi-skill foundational chain among true gaps."
    return "Foundational → surface: " + " → ".join(reversed(names))

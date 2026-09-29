"""WU-04 — JD demand closure, profile supply, zones, and pruned skill edges."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.constants import HAS_SKILL_SEED
from jd_agent.graphs.resume_generate.nodes.score_demand.profile_seeds import (
    profile_supply_seeds,
)
from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.integrations.skills_graph import get_skills_graph
from jd_agent.shared.gap_zones import (
    assign_zone,
    compute_gaps,
    personalized_pagerank,
)
from jd_agent.shared.skill_closures import (
    demand_closure,
    make_is_domain,
    scc_warn,
    supply_closure_noisy_or,
)
from jd_agent.shared.supply_edge_prune import prune_supply_edges

_DEFAULT_CLOSURE_WEIGHT = 1.0


def score_demand(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Compute demand baseline: closures, zones, fit, and ``edges_subset``."""

    _ = config
    jd_targets = list(state.get("jd_targets") or [])
    if not jd_targets:
        raise ValueError("jd_targets is required before score_demand")

    dossier = state.get("dossier")
    if not isinstance(dossier, dict):
        raise ValueError("dossier is required before score_demand")

    skills_graph = get_skills_graph()
    skill_meta: dict[str, dict[str, str]] = {
        nid: {"name": node.name, "skillType": node.skill_type}
        for nid, node in skills_graph.nodes.items()
    }
    edges = [(e.source, e.target, e.type) for e in skills_graph.edges]
    is_domain = make_is_domain(skill_meta)

    s_seed_raw, s_explicit_raw = profile_supply_seeds(
        dossier, has_skill_seed=HAS_SKILL_SEED
    )
    s_seed = {k: v for k, v in s_seed_raw.items() if k in skill_meta}
    s_explicit = {k: v for k, v in s_explicit_raw.items() if k in skill_meta}

    scc_warn(edges)

    d_seed = {
        str(t["skill_id"]): float(t["weight"])
        for t in jd_targets
        if str(t.get("skill_id") or "") in skill_meta
    }
    if not d_seed:
        raise ValueError("jd_targets did not resolve to any skills in the graph")

    d_star = demand_closure(d_seed, edges, is_domain)

    weights: dict[str, float] = {
        str(t["skill_id"]): float(t["weight"])
        for t in jd_targets
        if str(t.get("skill_id") or "") in skill_meta
    }
    for sid in d_star:
        weights.setdefault(sid, _DEFAULT_CLOSURE_WEIGHT)

    s_star_profile = supply_closure_noisy_or(s_seed, edges, is_domain)
    gaps_map, fit_profile = compute_gaps(d_star, s_star_profile, weights)

    held_ids = {sid for sid, val in s_explicit.items() if val > 0}
    ppr, rho = personalized_pagerank(edges, d_star, held_ids, is_domain)

    zones: dict[str, str] = {}
    latent_kind: dict[str, str] = {}
    for sid, dv in d_star.items():
        if dv <= 0:
            continue
        zone, kind = assign_zone(sid, s_explicit, s_star_profile, ppr, rho)
        zones[sid] = zone
        latent_kind[sid] = kind

    edges_subset = prune_supply_edges(edges, d_star, is_domain)

    listed_ids = [str(t["skill_id"]) for t in jd_targets]

    demand: dict[str, Any] = {
        "d_star": {k: round(v, 4) for k, v in d_star.items() if v > 0},
        "weights": {
            k: round(weights[k], 4) for k in d_star if d_star.get(k, 0) > 0
        },
        "s_star_profile": {
            k: round(s_star_profile.get(k, 0.0), 4)
            for k in d_star
            if d_star.get(k, 0) > 0
        },
        "zones": zones,
        "latent_kind": latent_kind,
        "fit_profile": round(fit_profile, 4),
        "edges_subset": edges_subset,
        "gaps": {
            k: round(gaps_map.get(k, 0.0), 4)
            for k in d_star
            if d_star.get(k, 0) > 0
        },
        "ppr_rho": round(rho, 6),
        "listed_jd_skill_ids": listed_ids,
    }
    return {"demand": demand}

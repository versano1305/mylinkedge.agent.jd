"""Compute closures, zones, themes, and interview candidates for a session.

Loads the global Skill graph once, resolves the JD's skills to nodes, runs the
demand/supply closures, partitions the demand closure into the three zones, and
assembles the display-ready ``review`` block plus the raw interview candidate
list (ranked downstream by ``rank_queue``).
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.gap_collect.state import GapCollectState
from jd_agent.integrations.skills_graph import get_skills_graph
from jd_agent.shared.gap_zones import (
    DEFAULT_WEIGHT,
    GAP_P,
    LATENT_DELTA,
    PPR_PERCENTILE,
    ZONE_CONFIRMED,
    ZONE_LATENT,
    ZONE_TRUE_GAP,
    assign_zone,
    build_themes,
    compute_gaps,
    critical_path,
    fit_if_latent_skills_confirmed,
    personalized_pagerank,
)
from jd_agent.shared.skill_closures import (
    demand_closure,
    make_is_domain,
    scc_warn,
    supply_closure_noisy_or,
)

_UNMET_ZONES = frozenset({ZONE_LATENT, ZONE_TRUE_GAP})

_PROBE_HINTS = {
    "requires_prerequisite_path": (
        "They hold prerequisites for this — ask how they applied those without "
        "naming the target skill."
    ),
    "bridge_neighbor": (
        "Anchor on a related skill they already have; ask how that work touched "
        "this area."
    ),
    "confirm_implied": (
        "The graph implies this. Ask one open question to confirm — never lead "
        "with the skill name."
    ),
    "open_recall": (
        "Open recall: ask what they worked on in this area and let them name the "
        "tools."
    ),
}


def compute_gaps_node(
    state: GapCollectState, config: RunnableConfig
) -> dict[str, Any]:
    """Build the ``gaps`` review payload and raw interview candidates."""
    _ = config
    jd_raw_skills = list(state.get("jd_raw_skills") or [])
    if not jd_raw_skills:
        raise ValueError("jd_raw_skills is required before compute_gaps")

    user_skill_ids = list(state.get("user_skill_ids") or [])
    evidence_ids = list(state.get("evidence_skill_ids") or user_skill_ids)

    graph = get_skills_graph()
    skill_meta: dict[str, dict[str, str]] = {
        nid: {"name": node.name, "skillType": node.skill_type}
        for nid, node in graph.nodes.items()
    }
    edges = [(e.source, e.target, e.type) for e in graph.edges]
    is_domain = make_is_domain(skill_meta)

    resolved, unresolved = _resolve_jd_skills(jd_raw_skills, skill_meta)
    jd_ids = [row["id"] for row in resolved]
    jd_meta_by_id = {row["id"]: row for row in resolved}
    listed_ids = set(jd_ids)

    held_ids = {sid for sid in user_skill_ids if sid in skill_meta}
    evidence_in_graph = {sid for sid in evidence_ids if sid in skill_meta}
    s_explicit = {sid: 1.0 for sid in evidence_in_graph}
    for sid in held_ids:
        s_explicit.setdefault(sid, 0.0)

    scc_warn(edges)

    d_seed = {sid: DEFAULT_WEIGHT for sid in jd_ids}
    d_star = demand_closure(d_seed, edges, is_domain)

    s_seed = {sid: 1.0 for sid in evidence_in_graph}
    if not s_seed and held_ids:
        s_seed = {sid: 1.0 for sid in held_ids}
    s_star = supply_closure_noisy_or(s_seed, edges, is_domain)

    weights = {sid: DEFAULT_WEIGHT for sid in jd_ids}
    for sid in d_star:
        weights.setdefault(sid, DEFAULT_WEIGHT)

    gaps_map, fit = compute_gaps(d_star, s_star, weights)
    ppr, rho = personalized_pagerank(
        edges, d_star, held_ids or evidence_in_graph, is_domain
    )

    # Per-skill rows over the whole demand closure, sorted by gap.
    skills_rows: list[dict[str, Any]] = []
    zone_of: dict[str, str] = {}
    for sid in sorted(d_star, key=lambda k: -gaps_map.get(k, 0.0)):
        zone, kind = assign_zone(sid, s_explicit, s_star, ppr, rho)
        zone_of[sid] = zone
        meta = skill_meta.get(sid, {})
        name = meta.get("name") or jd_meta_by_id.get(sid, {}).get("name") or sid
        stype = (
            meta.get("skillType")
            or jd_meta_by_id.get(sid, {}).get("skillType")
            or "unknown"
        )
        sv = float(s_star.get(sid, 0.0))
        skills_rows.append(
            {
                "skill_id": sid,
                "name": name,
                "skill_type": stype,
                "zone": zone,
                "latent_kind": kind,
                "requirement_level": _requirement_level(
                    jd_meta_by_id.get(sid, {}).get("requirement_level", 1.0)
                ),
                "listed_on_jd": sid in listed_ids,
                "weight": round(float(weights.get(sid, DEFAULT_WEIGHT)), 4),
                "d_star": round(float(d_star.get(sid, 0.0)), 4),
                "s_star": round(sv, 4),
                "s_explicit": float(s_explicit.get(sid, 0.0)),
                "ppr": round(float(ppr.get(sid, 0.0)), 6),
                "gap": round(float(gaps_map.get(sid, 0.0)), 4),
                "hard": sv <= 0.0,
            }
        )

    unmet_ids = {sid for sid, z in zone_of.items() if z in _UNMET_ZONES}
    themes = build_themes(edges, unmet_ids, zone_of, skill_meta)
    theme_of = {
        sid: str(theme["id"])
        for theme in themes
        for sid in theme["skill_ids"]  # type: ignore[union-attr]
    }
    true_gap_ids = {sid for sid, z in zone_of.items() if z == ZONE_TRUE_GAP}
    crit_sentence = critical_path(edges, true_gap_ids, skill_meta)

    zone_counts = Counter(zone_of.values())
    counts = {
        "confirmed": int(zone_counts.get(ZONE_CONFIRMED, 0)),
        "latent": int(zone_counts.get(ZONE_LATENT, 0)),
        "true_gap": int(zone_counts.get(ZONE_TRUE_GAP, 0)),
    }

    latent_ids = {sid for sid, z in zone_of.items() if z == ZONE_LATENT}
    fit_if_all_latent = fit_if_latent_skills_confirmed(
        d_star, s_seed, latent_ids, edges, is_domain, weights
    )
    fit_uplift_latent = max(0.0, fit_if_all_latent - fit)

    candidates = _build_interview_candidates(
        skills_rows, edges, held_ids, skill_meta, theme_of
    )

    gaps_doc: dict[str, Any] = {
        "schema_version": 1,
        "meta": {
            "fit": round(fit, 4),
            "fit_if_all_latent": round(fit_if_all_latent, 4),
            "fit_uplift_latent": round(fit_uplift_latent, 4),
            "zone_counts": counts,
            "jd_skill_count": len(jd_raw_skills),
            "resolved_count": len(jd_ids),
            "unresolved": unresolved,
            "thresholds": {
                "latent_delta": LATENT_DELTA,
                "ppr_rho": round(rho, 6),
                "ppr_percentile": PPR_PERCENTILE,
                "gap_p": GAP_P,
            },
        },
        "review": {
            "headline": _headline(fit, counts),
            "latent_fit": _latent_fit_review(
                fit, fit_if_all_latent, counts["latent"]
            ),
            "critical_path": crit_sentence,
            "themes": themes,
            "by_skill_type": _by_skill_type(skills_rows),
            "hard_vs_soft": _hard_vs_soft(skills_rows),
        },
        "skills": skills_rows,
    }

    return {"gaps": gaps_doc, "interview_candidates": candidates}


def _requirement_level(value: Any) -> float:
    """Read a priority in ``[0, 1]``. Missing or invalid values weigh ``1.0``."""

    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    number = float(value)
    if not math.isfinite(number):
        return 1.0
    return min(1.0, max(0.0, number))


def _resolve_jd_skills(
    jd_raw_skills: list[dict[str, Any]],
    skill_meta: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    name_to_id: dict[str, str] = {}
    for nid, meta in skill_meta.items():
        norm = (meta.get("name") or "").strip().casefold()
        if norm:
            name_to_id.setdefault(norm, nid)

    resolved: list[dict[str, Any]] = []
    unresolved: list[str] = []
    seen: set[str] = set()
    for raw in jd_raw_skills:
        sid = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        rid = sid if sid in skill_meta else name_to_id.get(name.casefold())
        if not rid:
            unresolved.append(name or sid)
            continue
        if rid in seen:
            continue
        seen.add(rid)
        resolved.append(
            {
                "id": rid,
                "name": skill_meta[rid].get("name") or name,
                "skillType": skill_meta[rid].get("skillType") or "unknown",
                "requirement_level": _requirement_level(raw.get("requirement_level")),
            }
        )
    return resolved, unresolved


def _build_interview_candidates(
    skills_rows: list[dict[str, Any]],
    edges: list[tuple[str, str, str]],
    held_ids: set[str],
    skill_meta: dict[str, dict[str, str]],
    theme_of: dict[str, str],
) -> list[dict[str, Any]]:
    undirected: dict[str, set[str]] = defaultdict(set)
    requires_children: dict[str, list[str]] = defaultdict(list)
    for u, v, r in edges:
        undirected[u].add(v)
        undirected[v].add(u)
        if r == "REQUIRES":
            requires_children[u].append(v)

    candidates: list[dict[str, Any]] = []
    for row in skills_rows:
        if row["zone"] not in _UNMET_ZONES:
            continue
        sid = row["skill_id"]

        held_prereq_names = [
            skill_meta.get(t, {}).get("name") or t
            for t in requires_children.get(sid, [])
            if t in held_ids
        ]
        bridge_ids = [t for t in sorted(undirected.get(sid, set())) if t in held_ids]
        bridge_names = [skill_meta.get(t, {}).get("name") or t for t in bridge_ids]

        technique = _select_technique(
            latent_kind=row["latent_kind"],
            has_held_prereq=bool(held_prereq_names),
            has_bridge=bool(bridge_ids),
        )

        candidates.append(
            {
                "skill_id": sid,
                "skill_name": row["name"],
                "skill_type": row["skill_type"],
                "zone": row["zone"],
                "latent_kind": row["latent_kind"],
                "s_star": row["s_star"],
                "ppr": row["ppr"],
                "gap": row["gap"],
                "weight": row["weight"],
                "theme_id": theme_of.get(sid, ""),
                "technique": technique,
                "bridge_skill_ids": bridge_ids[:3],
                "bridge_skill_names": bridge_names[:3],
                "prerequisite_names": held_prereq_names[:3],
                "probe_hint": _PROBE_HINTS[technique],
            }
        )
    return candidates


def _select_technique(
    *, latent_kind: str, has_held_prereq: bool, has_bridge: bool
) -> str:
    if has_held_prereq:
        return "requires_prerequisite_path"
    if has_bridge:
        return "bridge_neighbor"
    if latent_kind == "implied":
        return "confirm_implied"
    return "open_recall"


def _headline(fit: float, counts: dict[str, int]) -> str:
    return (
        f"{round(fit * 100)}% fit. {counts['confirmed']} matched, "
        f"{counts['latent']} you may already have, "
        f"{counts['true_gap']} to plan for."
    )


def _latent_fit_review(
    fit: float, fit_if_all_latent: float, latent_count: int
) -> dict[str, Any] | None:
    """Display-ready latent fit ceiling; omitted when there are no latent skills."""
    if latent_count <= 0:
        return None
    uplift = max(0.0, fit_if_all_latent - fit)
    return {
        "if_all_confirmed": round(fit_if_all_latent, 4),
        "uplift": round(uplift, 4),
        "uplift_percent_points": round(uplift * 100),
        "sentence": (
            f"If all {latent_count} hidden skills check out, fit could reach "
            f"{round(fit_if_all_latent * 100)}% "
            f"(+{round(uplift * 100)} pts)."
        ),
    }


def _by_skill_type(skills_rows: list[dict[str, Any]]) -> dict[str, Any]:
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "confirmed": 0,
            "latent": 0,
            "true_gap": 0,
            "total_gap": 0.0,
        }
    )
    for row in skills_rows:
        bucket = agg[row["skill_type"]]
        bucket[row["zone"]] += 1
        bucket["total_gap"] += float(row["gap"])
    return {
        stype: {**vals, "total_gap": round(vals["total_gap"], 4)}
        for stype, vals in agg.items()
    }


def _hard_vs_soft(skills_rows: list[dict[str, Any]]) -> dict[str, int]:
    hard = 0
    soft = 0
    for row in skills_rows:
        if row["zone"] == ZONE_CONFIRMED:
            continue
        if row["hard"]:
            hard += 1
        else:
            soft += 1
    return {"hard": hard, "soft": soft}

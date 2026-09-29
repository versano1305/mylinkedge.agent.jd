"""Constrained greedy atom selection."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.atom_supply_seeds import atom_supply_seeds
from jd_agent.graphs.resume_generate.constants import CONTEXT_SEED, LICENSE_TAU, MIN_GAIN
from jd_agent.graphs.resume_generate.nodes.allocate.tiers import (
    exp_promotion_group,
    line_pool_for_exp,
)
from jd_agent.graphs.resume_generate.nodes.allocate.work_instances import (
    experience_anchor,
    is_selectable_atom,
)
from jd_agent.shared.resume_fit import (
    delta_fit,
    merge_supply_seeds,
    resume_fit,
    supply_star,
)
from jd_agent.shared.skill_closures import Edge, IsDomain, SupplyFanout


def _atom_by_id(atoms: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(a["atom_id"]): a for a in atoms if a.get("atom_id")}


def _seeds_for_selected(
    selected_ids: list[str],
    atom_map: dict[str, dict[str, Any]],
    context_by_instance: dict[str, list[str]],
) -> dict[str, float]:
    parts = [
        atom_supply_seeds(atom_map[aid], context_by_instance, context_seed=CONTEXT_SEED)
        for aid in selected_ids
        if aid in atom_map
    ]
    return merge_supply_seeds(*parts) if parts else {}


def _group_selected_count(
    group: frozenset[str], selected: dict[str, list[str]]
) -> int:
    return sum(len(selected.get(exp_id, [])) for exp_id in group)


def _marginal_gain(
    atom: dict[str, Any],
    coverage_seeds: dict[str, float],
    d_star: dict[str, float],
    weights: dict[str, float],
    edges: list[Edge],
    is_domain: IsDomain,
    context_by_instance: dict[str, list[str]],
    fanout: SupplyFanout | None,
) -> float:
    add = atom_supply_seeds(atom, context_by_instance, context_seed=CONTEXT_SEED)
    delta = delta_fit(coverage_seeds, add, d_star, weights, edges, is_domain, fanout)
    return delta * float(atom.get("strength") or 0.0)


def covered_jd_skill_ids(
    d_star: dict[str, float],
    seeds: dict[str, float],
    edges: list[Edge],
    is_domain: IsDomain,
    selected_atoms: list[dict[str, Any]],
    *,
    license_tau: float = LICENSE_TAU,
    fanout: SupplyFanout | None = None,
) -> list[str]:
    s_star = supply_star(seeds, edges, is_domain, fanout)
    covered: set[str] = set()
    for jid, dv in d_star.items():
        if dv <= 0:
            continue
        if s_star.get(jid, 0.0) >= license_tau:
            covered.add(jid)
    for atom in selected_atoms:
        for term in atom.get("licensed") or []:
            if not isinstance(term, dict):
                continue
            if term.get("via") == "explicit":
                jid = str(term.get("jd_skill_id") or "")
                if jid:
                    covered.add(jid)
    return sorted(covered)


def select_atoms(
    atoms: list[dict[str, Any]],
    instance_order: list[str],
    atoms_by_exp: dict[str, list[dict[str, Any]]],
    tiers: dict[str, str],
    promotion_groups_map: dict[str, list[str]],
    d_star: dict[str, float],
    weights: dict[str, float],
    edges: list[Edge],
    is_domain: IsDomain,
    context_by_instance: dict[str, list[str]],
    *,
    max_highlights_total: int,
    min_gain: float = MIN_GAIN,
    fanout: SupplyFanout | None = None,
) -> tuple[dict[str, list[str]], dict[str, float]]:
    """Return ``selected`` atom ids per experience and per-atom gain scores."""

    atom_map = _atom_by_id(atoms)
    selected: dict[str, list[str]] = {exp_id: [] for exp_id in instance_order}
    gain_by_atom: dict[str, float] = {}
    global_seeds: dict[str, float] = {}

    def coverage_seeds_for(exp_id: str) -> dict[str, float]:
        group = exp_promotion_group(exp_id, promotion_groups_map)
        ids: list[str] = []
        for member in group:
            ids.extend(selected.get(member, []))
        return _seeds_for_selected(ids, atom_map, context_by_instance)

    def total_selected() -> int:
        return sum(len(v) for v in selected.values())

    def can_add(exp_id: str) -> bool:
        if total_selected() >= max_highlights_total:
            return False
        group = exp_promotion_group(exp_id, promotion_groups_map)
        pool = line_pool_for_exp(exp_id, tiers, promotion_groups_map)
        if pool <= 0:
            return False
        if _group_selected_count(group, selected) >= pool:
            return False
        return True

    # Minimum-one line per experience with tier budget > 0 and selectable atoms.
    for exp_id, exp_atoms in atoms_by_exp.items():
        pool = line_pool_for_exp(exp_id, tiers, promotion_groups_map)
        if pool <= 0 or not exp_atoms:
            continue
        if not can_add(exp_id):
            continue
        cov = coverage_seeds_for(exp_id)
        best = max(
            exp_atoms,
            key=lambda a: _marginal_gain(
                a, cov, d_star, weights, edges, is_domain, context_by_instance, fanout
            ),
        )
        gain = _marginal_gain(
            best, cov, d_star, weights, edges, is_domain, context_by_instance, fanout
        )
        selected[exp_id].append(str(best["atom_id"]))
        gain_by_atom[str(best["atom_id"])] = gain
        global_seeds = merge_supply_seeds(
            global_seeds,
            atom_supply_seeds(best, context_by_instance, context_seed=CONTEXT_SEED),
        )

    while total_selected() < max_highlights_total:
        best_atom: dict[str, Any] | None = None
        best_gain = 0.0
        best_exp = ""

        for atom in atoms:
            if not is_selectable_atom(atom):
                continue
            aid = str(atom["atom_id"])
            if any(aid in sel for sel in selected.values()):
                continue
            exp_id = experience_anchor(atom)
            if exp_id not in selected:
                continue
            if not can_add(exp_id):
                continue
            cov = coverage_seeds_for(exp_id)
            gain = _marginal_gain(
                atom, cov, d_star, weights, edges, is_domain, context_by_instance, fanout
            )
            if gain > best_gain:
                best_gain = gain
                best_atom = atom
                best_exp = exp_id

        if best_atom is None or best_gain < min_gain:
            break
        aid = str(best_atom["atom_id"])
        selected[best_exp].append(aid)
        gain_by_atom[aid] = best_gain
        global_seeds = merge_supply_seeds(
            global_seeds,
            atom_supply_seeds(
                best_atom, context_by_instance, context_seed=CONTEXT_SEED
            ),
        )

    fit = resume_fit(d_star, weights, global_seeds, edges, is_domain, fanout)
    return selected, {"resume_fit": fit, "gain_by_atom": gain_by_atom}

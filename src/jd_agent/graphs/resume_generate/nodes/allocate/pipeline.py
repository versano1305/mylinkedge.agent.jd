"""Orchestration for WU-07 allocation."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.constants import (
    DEFAULT_TEMPLATE,
    MAX_HIGHLIGHTS_ONE_PAGE,
    MAX_HIGHLIGHTS_TWO_PAGES,
)
from jd_agent.graphs.resume_generate.models import Allocation
from jd_agent.graphs.resume_generate.nodes.allocate.relevance import role_relevance
from jd_agent.graphs.resume_generate.nodes.allocate.select import (
    covered_jd_skill_ids,
    select_atoms,
)
from jd_agent.graphs.resume_generate.nodes.allocate.tiers import (
    assign_tiers,
    promotion_groups,
    tier_budget_caps,
)
from jd_agent.graphs.resume_generate.nodes.allocate.work_instances import (
    experience_instances,
    index_atoms_by_experience,
)
from jd_agent.graphs.resume_generate.atom_supply_seeds import (
    atom_supply_seeds,
    build_context_skills_by_instance,
)
from jd_agent.graphs.resume_generate.constants import CONTEXT_SEED
from jd_agent.shared.resume_fit import delta_fit, merge_supply_seeds
from jd_agent.shared.skill_closures import Edge, IsDomain


def _max_highlights(template: dict[str, Any]) -> int:
    explicit = template.get("max_highlights_total")
    if isinstance(explicit, int) and explicit > 0:
        return explicit
    if template.get("page_budget") == 1:
        return MAX_HIGHLIGHTS_ONE_PAGE
    return MAX_HIGHLIGHTS_TWO_PAGES


def _ensure_standalone_values(
    atoms: list[dict[str, Any]],
    context_by_instance: dict[str, list[str]],
    d_star: dict[str, float],
    weights: dict[str, float],
    edges: list[Edge],
    is_domain: IsDomain,
) -> None:
    for atom in atoms:
        if atom.get("standalone_value") is not None:
            continue
        seeds = atom_supply_seeds(atom, context_by_instance, context_seed=CONTEXT_SEED)
        delta = delta_fit({}, seeds, d_star, weights, edges, is_domain)
        atom["standalone_value"] = delta * float(atom.get("strength") or 0.0)


def run_allocation(
    dossier: dict[str, Any],
    atoms: list[dict[str, Any]],
    demand: dict[str, Any],
    template: dict[str, Any],
    jd_context: dict[str, Any],
    edges: list[Edge],
    is_domain: IsDomain,
) -> Allocation:
    """Build the full allocation payload."""

    _ = jd_context
    d_star = {k: float(v) for k, v in (demand.get("d_star") or {}).items()}
    weights = {k: float(v) for k, v in (demand.get("weights") or {}).items()}
    edges_subset = list(demand.get("edges_subset") or edges)

    context_by_instance = build_context_skills_by_instance(atoms)
    _ensure_standalone_values(
        atoms, context_by_instance, d_star, weights, edges_subset, is_domain
    )

    exp_rows = experience_instances(dossier)
    instance_order = [e.instance_id for e in exp_rows]
    instances_by_id = {e.instance_id: e for e in exp_rows}
    atoms_by_exp = index_atoms_by_experience(atoms)

    d_star_ids = set(d_star)
    relevance = {
        exp_id: role_relevance(exp_id, instances_by_id[exp_id], atoms_by_exp.get(exp_id, []), d_star_ids)
        for exp_id in instance_order
        if exp_id in instances_by_id
    }

    tiers = assign_tiers(instance_order, instances_by_id, relevance, atoms_by_exp)
    groups = promotion_groups(instance_order, instances_by_id)
    budgets = tier_budget_caps(tiers)

    selected, metrics = select_atoms(
        atoms,
        instance_order,
        atoms_by_exp,
        tiers,
        groups,
        d_star,
        weights,
        edges_subset,
        is_domain,
        context_by_instance,
        max_highlights_total=_max_highlights(template or DEFAULT_TEMPLATE),
    )

    selected_atoms = [
        a for a in atoms if str(a.get("atom_id")) in {aid for ids in selected.values() for aid in ids}
    ]
    global_seeds = merge_supply_seeds(
        *[
            atom_supply_seeds(a, context_by_instance, context_seed=CONTEXT_SEED)
            for a in selected_atoms
        ]
    )
    covered = covered_jd_skill_ids(
        d_star, global_seeds, edges_subset, is_domain, selected_atoms
    )

    return Allocation(
        instance_order=instance_order,
        tiers=tiers,
        budgets=budgets,
        selected=selected,
        promotion_groups=groups,
        resume_fit=float(metrics["resume_fit"]),
        covered_jd_skill_ids=covered,
    )

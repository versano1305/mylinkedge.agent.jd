"""Enrich atoms with licensed terms and standalone value."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.atom_supply_seeds import (
    atom_supply_seeds,
    build_context_skills_by_instance,
)
from jd_agent.graphs.resume_generate.constants import CONTEXT_SEED, LICENSE_TAU
from jd_agent.graphs.resume_generate.nodes.license_and_value.instance_domain import (
    instance_domain_skill_ids,
)
from jd_agent.shared.atom_licensing import (
    partition_demand_skill_terms,
    partition_domain_skill_terms,
)
from jd_agent.shared.resume_fit import delta_fit, supply_star
from jd_agent.shared.skill_closures import Edge, IsDomain


def enrich_atoms(
    atoms: list[dict[str, Any]],
    *,
    dossier: dict[str, Any],
    demand: dict[str, Any],
    jd_targets: list[dict[str, Any]],
    jd_domains: list[dict[str, Any]],
    edges_subset: list[Edge],
    is_domain: IsDomain,
    license_tau: float = LICENSE_TAU,
    context_seed: float = CONTEXT_SEED,
) -> list[dict[str, Any]]:
    """Return atoms with ``licensed``, ``adjacent``, and ``standalone_value``."""

    d_star = {k: float(v) for k, v in (demand.get("d_star") or {}).items()}
    weights = {k: float(v) for k, v in (demand.get("weights") or {}).items()}
    profile_zones = demand.get("zones") if isinstance(demand.get("zones"), dict) else {}
    profile_latent_kind = (
        demand.get("latent_kind") if isinstance(demand.get("latent_kind"), dict) else {}
    )

    jd_rows_by_id = {
        str(row.get("skill_id") or "").strip(): row
        for row in jd_targets
        if str(row.get("skill_id") or "").strip()
    }

    context_by_instance = build_context_skills_by_instance(atoms)
    domain_by_instance = instance_domain_skill_ids(dossier, jd_domains)

    enriched: list[dict[str, Any]] = []
    for raw in atoms:
        atom = dict(raw)
        skill_ids = {
            str(s).strip()
            for s in (atom.get("skill_ids") or [])
            if str(s).strip()
        }
        inst = str(atom.get("instance_id") or "").strip()
        parent = str(atom.get("parent_instance_id") or "").strip()
        instance_domains = set(domain_by_instance.get(inst, set()))
        if parent:
            instance_domains |= domain_by_instance.get(parent, set())

        seeds = atom_supply_seeds(atom, context_by_instance, context_seed=context_seed)
        s_star_atom = supply_star(seeds, edges_subset, is_domain)

        demand_lic, adjacent = partition_demand_skill_terms(
            atom_skill_ids=skill_ids,
            s_star_atom=s_star_atom,
            d_star=d_star,
            jd_rows_by_id=jd_rows_by_id,
            profile_zones=profile_zones,
            profile_latent_kind=profile_latent_kind,
            license_tau=license_tau,
        )
        domain_lic = partition_domain_skill_terms(
            atom_skill_ids=skill_ids,
            instance_domain_ids=instance_domains,
            jd_domain_rows=jd_domains,
        )

        licensed = demand_lic + domain_lic
        atom["licensed"] = licensed
        atom["adjacent"] = adjacent

        strength = float(atom.get("strength") or 0.0)
        if strength > 0 and str(atom.get("text") or "").strip():
            delta = delta_fit({}, seeds, d_star, weights, edges_subset, is_domain)
            atom["standalone_value"] = round(delta * strength, 6)
        else:
            atom["standalone_value"] = 0.0

        enriched.append(atom)
    return enriched

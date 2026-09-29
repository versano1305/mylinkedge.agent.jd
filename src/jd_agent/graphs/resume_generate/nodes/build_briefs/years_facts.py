"""Years-of-experience facts for summary generation (WU-10)."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.models import Instance
from jd_agent.graphs.resume_generate.nodes.allocate.work_instances import (
    experience_instances,
)
from jd_agent.shared.experience_intervals import experience_range, union_years


def _atoms_by_experience(atoms: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_exp: dict[str, list[dict[str, Any]]] = {}
    for atom in atoms:
        if not isinstance(atom, dict):
            continue
        parent = str(atom.get("parent_instance_id") or "").strip()
        exp_id = parent or str(atom.get("instance_id") or "").strip()
        if not exp_id:
            continue
        by_exp.setdefault(exp_id, []).append(atom)
    return by_exp


def _licenses_jd_skill(atom: dict[str, Any], jd_skill_id: str) -> bool:
    for term in atom.get("licensed") or []:
        if not isinstance(term, dict):
            continue
        if str(term.get("jd_skill_id") or "") == jd_skill_id:
            return True
    return False


def _exp_licenses_skill(
    exp_id: str,
    jd_skill_id: str,
    instance: Instance,
    atoms_on_exp: list[dict[str, Any]],
) -> bool:
    for atom in atoms_on_exp:
        if _licenses_jd_skill(atom, jd_skill_id):
            return True
    for sk in instance.skills:
        if str(sk.id) == jd_skill_id:
            return True
    return False


def build_years_facts(
    dossier: dict[str, Any],
    atoms: list[dict[str, Any]],
    jd_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Total career years and per–must-have skill unions."""

    exp_rows = experience_instances(dossier)
    all_ranges = []
    for inst in exp_rows:
        rng = experience_range(inst.start, inst.end)
        if rng is not None:
            all_ranges.append(rng)

    total_years = union_years(all_ranges) if all_ranges else 0.0
    atoms_by_exp = _atoms_by_experience(atoms)
    instances_by_id = {e.instance_id: e for e in exp_rows}

    per_skill: dict[str, Any] = {}
    for target in jd_targets:
        if not isinstance(target, dict):
            continue
        importance = str(target.get("importance") or "must")
        min_years = target.get("min_years")
        if importance != "must" or min_years is None:
            continue
        try:
            min_y = int(min_years)
        except (TypeError, ValueError):
            continue
        skill_id = str(target.get("skill_id") or "").strip()
        if not skill_id:
            continue

        ranges = []
        matched_exp: list[str] = []
        for exp_id, inst in instances_by_id.items():
            if not _exp_licenses_skill(
                exp_id, skill_id, inst, atoms_by_exp.get(exp_id, [])
            ):
                continue
            rng = experience_range(inst.start, inst.end)
            if rng is None:
                continue
            ranges.append(rng)
            matched_exp.append(exp_id)

        union = union_years(ranges) if ranges else 0.0
        per_skill[skill_id] = {
            "min_years": min_y,
            "union_years": round(union, 2),
            "qualifier_met": union >= float(min_y),
            "instance_ids": matched_exp,
        }

    return {
        "total_years": round(total_years, 2),
        "per_skill": per_skill,
    }

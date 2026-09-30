"""Per-experience generation briefs."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.models import (
    Allocation,
    BriefAtom,
    BriefTense,
    Instance,
    InstanceBrief,
)
from jd_agent.graphs.resume_generate.nodes.allocate.work_instances import (
    experience_instances,
)


def _atom_map(atoms: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(a["atom_id"]): a
        for a in atoms
        if isinstance(a, dict) and a.get("atom_id")
    }


def _licensed_surface_forms(atom: dict[str, Any]) -> list[str]:
    forms: list[str] = []
    for term in atom.get("licensed") or []:
        if not isinstance(term, dict):
            continue
        form = str(term.get("surface_form") or "").strip()
        if form and form not in forms:
            forms.append(form)
    return forms


def is_generatable_brief(brief: InstanceBrief) -> bool:
    """Instances with no selected atoms skip the highlight LLM (tier D, etc.)."""
    return brief.budget > 0 and bool(brief.atoms)


def generatable_instance_ids(
    instance_briefs: dict[str, InstanceBrief],
    allocation: Allocation,
) -> list[str]:
    """Stable order for WU-09 Send fan-out (unique ids only)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for iid in allocation.instance_order:
        if iid in seen:
            continue
        if iid not in instance_briefs or not is_generatable_brief(instance_briefs[iid]):
            continue
        seen.add(iid)
        ordered.append(iid)
    return ordered


def build_instance_briefs(
    dossier: dict[str, Any],
    allocation: Allocation,
    atoms: list[dict[str, Any]],
) -> dict[str, InstanceBrief]:
    """One brief per experience in allocation order (tier D included)."""

    exp_rows = experience_instances(dossier)
    by_id = {e.instance_id: e for e in exp_rows}
    atoms_by_id = _atom_map(atoms)
    briefs: dict[str, InstanceBrief] = {}

    for exp_id in allocation.instance_order:
        inst = by_id.get(exp_id)
        if inst is None:
            continue
        selected_ids = list(allocation.selected.get(exp_id) or [])
        brief_atoms: list[BriefAtom] = []
        for aid in selected_ids:
            atom = atoms_by_id.get(aid)
            if atom is None:
                continue
            brief_atoms.append(
                BriefAtom(
                    atom_id=aid,
                    text=str(atom.get("text") or ""),
                    metrics=[
                        str(m) for m in (atom.get("metrics") or []) if str(m).strip()
                    ],
                    licensed=_licensed_surface_forms(atom),
                )
            )
        tense: BriefTense = "present" if inst.end is None else "past"
        briefs[exp_id] = InstanceBrief(
            instance_id=exp_id,
            company=inst.company,
            position=inst.position,
            startDate=inst.start,
            endDate=inst.end,
            location=inst.location,
            employmentType=inst.employment_type,
            teamSize=inst.team_size,
            industry=inst.industry,
            company_description=inst.company_description,
            budget=len(brief_atoms),
            tense=tense,
            atoms=brief_atoms,
        )

    return briefs

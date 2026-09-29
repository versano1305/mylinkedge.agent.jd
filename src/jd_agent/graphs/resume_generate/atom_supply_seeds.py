"""Map resume atoms to supply-closure seeds (WU-06 / WU-07)."""

from __future__ import annotations

from typing import Any


def build_context_skills_by_instance(atoms: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Context-bucket skills keyed by experience or child instance id."""

    by_instance: dict[str, list[str]] = {}
    for atom in atoms:
        text = str(atom.get("text") or "").strip()
        if text:
            continue
        skill_ids = [
            str(s)
            for s in (atom.get("skill_ids") or [])
            if str(s).strip()
        ]
        if not skill_ids:
            continue
        inst = str(atom.get("instance_id") or "")
        parent = str(atom.get("parent_instance_id") or "")
        for key in (inst, parent):
            if not key:
                continue
            bucket = by_instance.setdefault(key, [])
            for sid in skill_ids:
                if sid not in bucket:
                    bucket.append(sid)
    return by_instance


def atom_supply_seeds(
    atom: dict[str, Any],
    context_by_instance: dict[str, list[str]],
    *,
    context_seed: float,
) -> dict[str, float]:
    """Seeds for one atom: explicit skills at 1.0, context bucket at ``context_seed``."""

    seeds: dict[str, float] = {}
    for sid in atom.get("skill_ids") or []:
        s = str(sid).strip()
        if s:
            seeds[s] = 1.0

    inst = str(atom.get("instance_id") or "")
    parent = str(atom.get("parent_instance_id") or "")
    for anchor in (inst, parent):
        if not anchor:
            continue
        for sid in context_by_instance.get(anchor, []):
            seeds[sid] = max(seeds.get(sid, 0.0), context_seed)
    return seeds

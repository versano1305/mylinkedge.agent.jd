"""Experience anchors and atom indexing for allocation."""

from __future__ import annotations

from datetime import date
from typing import Any

from jd_agent.graphs.resume_generate.models import Instance
from jd_agent.shared.experience_intervals import parse_ym as _parse_ym


def months_since_end(end: str | None, *, today: date | None = None) -> float | None:
    """Months from role end to ``today``; ``None`` end means present (0 months)."""

    ref = today or date.today()
    if end is None:
        return 0.0
    parsed = _parse_ym(end)
    if parsed is None:
        return None
    y, m = parsed
    return (ref.year - y) * 12 + (ref.month - m)


def experience_anchor(atom: dict[str, Any]) -> str:
    """Roll child atoms up to their owning ExperienceEvent id."""

    parent = str(atom.get("parent_instance_id") or "").strip()
    if parent:
        return parent
    return str(atom.get("instance_id") or "").strip()


def is_selectable_atom(atom: dict[str, Any]) -> bool:
    return bool(str(atom.get("text") or "").strip()) and bool(
        str(atom.get("atom_id") or "").strip()
    )


def experience_instances(dossier: dict[str, Any]) -> list[Instance]:
    """ExperienceEvent rows from the dossier, reverse-chronological."""

    rows: list[Instance] = []
    for raw in dossier.get("instances") or []:
        if not isinstance(raw, dict):
            continue
        inst = Instance.model_validate(raw)
        if inst.parent_instance_id is not None:
            continue
        if inst.node_label and inst.node_label != "ExperienceEvent":
            continue
        rows.append(inst)

    def sort_key(item: Instance) -> tuple[int, int, int, str]:
        end_key = _parse_ym(item.end) or (9999, 12)
        start_key = _parse_ym(item.start) or (0, 1)
        return (-end_key[0], -end_key[1], -start_key[0], item.instance_id)

    rows.sort(key=sort_key)
    return rows


def index_atoms_by_experience(
    atoms: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Map ExperienceEvent id → selectable atoms attached to that role."""

    by_exp: dict[str, list[dict[str, Any]]] = {}
    for atom in atoms:
        if not is_selectable_atom(atom):
            continue
        exp_id = experience_anchor(atom)
        if not exp_id:
            continue
        by_exp.setdefault(exp_id, []).append(atom)
    return by_exp

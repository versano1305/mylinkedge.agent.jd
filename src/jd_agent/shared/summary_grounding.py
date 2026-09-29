"""Allow-lists for grounded ``basics.summary`` generation (WU-10 / WU-11)."""

from __future__ import annotations

from typing import Any

from jd_agent.shared.years_display import (
    career_year_allowlist,
    format_career_years,
    skill_year_allowlist,
)


def collect_resume_surface_terms(
    generated: dict[str, Any],
    static_skills: list[dict[str, Any]],
) -> set[str]:
    """JD/skill strings already present on the resume body."""

    terms: set[str] = set()
    for payload in generated.values():
        if not isinstance(payload, dict):
            continue
        for highlight in payload.get("highlights") or []:
            if not isinstance(highlight, dict):
                continue
            text = str(highlight.get("text") or "")
            if text.strip():
                terms.add(text.strip())
            for term in highlight.get("jd_terms_used") or []:
                t = str(term).strip()
                if t:
                    terms.add(t)
    for group in static_skills:
        if not isinstance(group, dict):
            continue
        for kw in group.get("keywords") or []:
            t = str(kw).strip()
            if t:
                terms.add(t)
    return terms


def allowed_summary_terms(
    generated: dict[str, Any],
    static_skills: list[dict[str, Any]],
    *,
    skill_group_labels: list[str] | None = None,
) -> set[str]:
    """Terms the summary may name (must appear in highlights or skills)."""

    allowed: set[str] = set()
    for group in static_skills:
        if not isinstance(group, dict):
            continue
        name = str(group.get("name") or "").strip()
        if name:
            allowed.add(name)
        for kw in group.get("keywords") or []:
            t = str(kw).strip()
            if t:
                allowed.add(t)
    for label in skill_group_labels or []:
        t = str(label).strip()
        if t:
            allowed.add(t)
    for payload in generated.values():
        if not isinstance(payload, dict):
            continue
        for highlight in payload.get("highlights") or []:
            if not isinstance(highlight, dict):
                continue
            for term in highlight.get("jd_terms_used") or []:
                t = str(term).strip()
                if t:
                    allowed.add(t)
    return allowed


def selected_atom_ids(allocation: dict[str, Any]) -> set[str]:
    selected = allocation.get("selected") or {}
    ids: set[str] = set()
    if not isinstance(selected, dict):
        return ids
    for atom_list in selected.values():
        if isinstance(atom_list, list):
            ids.update(str(a) for a in atom_list if str(a).strip())
    return ids


def pick_flagship_metric(
    atoms: list[dict[str, Any]],
    selected_ids: set[str],
) -> dict[str, str] | None:
    """Best achievement metric among selected atoms."""

    candidates: list[tuple[float, str, str, str]] = []
    for atom in atoms:
        if not isinstance(atom, dict):
            continue
        aid = str(atom.get("atom_id") or "")
        if aid not in selected_ids:
            continue
        if str(atom.get("kind") or "") != "achievement":
            continue
        metrics = [str(m).strip() for m in (atom.get("metrics") or []) if str(m).strip()]
        if not metrics:
            continue
        strength = float(atom.get("strength") or 0.0)
        candidates.append((strength, metrics[0], aid, str(atom.get("text") or "")))
    if not candidates:
        for atom in atoms:
            if not isinstance(atom, dict):
                continue
            aid = str(atom.get("atom_id") or "")
            if aid not in selected_ids:
                continue
            metrics = [str(m).strip() for m in (atom.get("metrics") or []) if str(m).strip()]
            if not metrics:
                continue
            strength = float(atom.get("strength") or 0.0)
            candidates.append(
                (strength, metrics[0], aid, str(atom.get("text") or ""))
            )
    if not candidates:
        return None
    candidates.sort(key=lambda row: (-row[0], row[1]))
    _, metric, atom_id, source = candidates[0]
    return {"metric": metric, "atom_id": atom_id, "source_text": source}


def build_years_allowlist(years_facts: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    total = years_facts.get("total_years")
    if isinstance(total, (int, float)):
        allowed |= career_year_allowlist(float(total))
        display = format_career_years(float(total))
        if display:
            allowed.add(display)
    per_skill = years_facts.get("per_skill")
    if isinstance(per_skill, dict):
        for entry in per_skill.values():
            if not isinstance(entry, dict) or not entry.get("qualifier_met"):
                continue
            union = entry.get("union_years")
            if isinstance(union, (int, float)):
                allowed |= skill_year_allowlist(float(union))
    return allowed


def allowed_summary_numbers(
    atoms: list[dict[str, Any]],
    selected_ids: set[str],
    years_facts: dict[str, Any],
    flagship_metric: str | None,
) -> set[str]:
    """Numbers the summary may claim."""

    allowed = build_years_allowlist(years_facts)
    if flagship_metric:
        allowed.add(flagship_metric.strip())
    for atom in atoms:
        if not isinstance(atom, dict):
            continue
        aid = str(atom.get("atom_id") or "")
        if aid not in selected_ids:
            continue
        for m in atom.get("metrics") or []:
            t = str(m).strip()
            if t:
                allowed.add(t)
    return allowed

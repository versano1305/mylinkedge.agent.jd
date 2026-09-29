"""Deterministic payload for ``basics.summary`` generation."""

from __future__ import annotations

from typing import Any

from jd_agent.shared.summary_grounding import (
    allowed_summary_numbers,
    allowed_summary_terms,
    pick_flagship_metric,
    selected_atom_ids,
)
from jd_agent.shared.years_display import format_career_years, format_skill_years


def build_summary_context(state: dict[str, Any]) -> dict[str, Any]:
    """Assemble facts and allow-lists from graph state."""

    briefs = state.get("briefs") if isinstance(state.get("briefs"), dict) else {}
    static = briefs.get("static") if isinstance(briefs.get("static"), dict) else {}
    basics = static.get("basics") if isinstance(static.get("basics"), dict) else {}
    static_skills = list(static.get("skills") or [])
    years_facts = briefs.get("years_facts") if isinstance(briefs.get("years_facts"), dict) else {}
    group_labels = list(briefs.get("skill_group_labels") or [])

    generated = state.get("generated") if isinstance(state.get("generated"), dict) else {}
    allocation = state.get("allocation") if isinstance(state.get("allocation"), dict) else {}
    atoms = list(state.get("atoms") or [])
    jd_context = state.get("jd_context") if isinstance(state.get("jd_context"), dict) else {}
    jd_targets = list(state.get("jd_targets") or [])

    selected_ids = selected_atom_ids(allocation)
    flagship = pick_flagship_metric(atoms, selected_ids)

    allowed_terms = allowed_summary_terms(
        generated, static_skills, skill_group_labels=group_labels
    )
    allowed_numbers = allowed_summary_numbers(
        atoms,
        selected_ids,
        years_facts,
        flagship["metric"] if flagship else None,
    )

    highlights: list[str] = []
    for payload in generated.values():
        if not isinstance(payload, dict):
            continue
        for row in payload.get("highlights") or []:
            if isinstance(row, dict):
                text = str(row.get("text") or "").strip()
                if text:
                    highlights.append(text)

    total_years = float(years_facts.get("total_years") or 0.0)
    per_skill_qualified: list[dict[str, str]] = []
    per_skill_omit: list[str] = []
    per_skill = years_facts.get("per_skill")
    surface_by_id = {
        str(t.get("skill_id") or ""): str(t.get("surface_form") or t.get("name") or "")
        for t in jd_targets
        if isinstance(t, dict)
    }
    if isinstance(per_skill, dict):
        for skill_id, entry in per_skill.items():
            if not isinstance(entry, dict):
                continue
            name = surface_by_id.get(str(skill_id), str(skill_id))
            if entry.get("qualifier_met"):
                union = float(entry.get("union_years") or 0.0)
                per_skill_qualified.append(
                    {
                        "surface_form": name,
                        "years_display": format_skill_years(union),
                        "min_years": str(entry.get("min_years") or ""),
                    }
                )
            else:
                if entry.get("min_years") is not None:
                    per_skill_omit.append(name)

    domain_terms: list[str] = []
    jd_domains = list(state.get("jd_domains") or [])
    for row in jd_domains:
        if not isinstance(row, dict):
            continue
        form = str(row.get("surface_form") or row.get("name") or "").strip()
        if form and form in allowed_terms:
            domain_terms.append(form)

    return {
        "label": str(basics.get("label") or ""),
        "jd_title": str(jd_context.get("title") or ""),
        "jd_company": str(jd_context.get("company_name") or ""),
        "skill_group_labels": group_labels,
        "domain_terms": domain_terms,
        "years": {
            "total_years": total_years,
            "total_years_display": format_career_years(total_years),
            "per_skill_qualified": per_skill_qualified,
            "per_skill_omit": per_skill_omit,
        },
        "flagship_metric": flagship,
        "highlights": highlights,
        "skills_keywords": [
            str(kw).strip()
            for group in static_skills
            if isinstance(group, dict)
            for kw in (group.get("keywords") or [])
            if str(kw).strip()
        ],
        "allowed_terms": sorted(allowed_terms),
        "allowed_numbers": sorted(allowed_numbers),
    }


def has_summary_content(context: dict[str, Any]) -> bool:
    return bool(context.get("highlights") or context.get("skills_keywords"))

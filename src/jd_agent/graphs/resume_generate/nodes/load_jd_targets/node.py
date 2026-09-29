"""Resolve JD skills into weighted demand seeds and summary context.

``importance`` on each stored skill is already a float in ``[0, 1]`` and is
the demand weight. Missing or non-numeric importance falls back to ``1.0``.
Domain skills are returned separately so later closures do not seed them.
"""

from __future__ import annotations

import math
from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.postgres import JobDescription

from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.integrations.skills_graph import get_skills_graph
from jd_agent.shared.skill_closures import DOMAIN_SKILL_TYPE

_REQUIREMENTS_SECTION = "requirements"


def load_jd_targets(state: ResumeGenerateState, config: RunnableConfig) -> dict[str, Any]:
    """Resolve JD skills to graph ids and split Domain skills aside."""

    _ = config
    jd = state.get("jd")
    if not isinstance(jd, JobDescription):
        raise ValueError("jd must be loaded before load_jd_targets")
    if not jd.skills:
        raise ValueError(f"job_description {jd.id} has no extracted skills; run jd_extract first")

    skill_meta = _skill_meta(get_skills_graph())
    name_to_id = _name_index(skill_meta)
    rows, unresolved = _resolve_skills(jd.skills, skill_meta, name_to_id)
    targets = [row for row in rows if row["skill_type"] != DOMAIN_SKILL_TYPE]
    domains = [row for row in rows if row["skill_type"] == DOMAIN_SKILL_TYPE]

    return {
        "jd_targets": targets,
        "jd_domains": domains,
        "jd_context": {
            "title": jd.title_name,
            "company_name": jd.company_name,
            "requirements": _requirements_text(jd.sections),
            "unresolved": unresolved,
        },
    }


def _skill_meta(graph: Any) -> dict[str, dict[str, str]]:
    return {
        nid: {"name": node.name, "skillType": node.skill_type} for nid, node in graph.nodes.items()
    }


def _name_index(skill_meta: dict[str, dict[str, str]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for nid, meta in skill_meta.items():
        norm = (meta.get("name") or "").strip().casefold()
        if norm:
            index.setdefault(norm, nid)
    return index


def _resolve_skills(
    skills: list[Any],
    skill_meta: dict[str, dict[str, str]],
    name_to_id: dict[str, str],
) -> tuple[list[dict[str, Any]], list[str]]:
    resolved: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    unresolved: list[str] = []

    for skill in skills:
        raw = skill.model_dump() if hasattr(skill, "model_dump") else dict(skill)
        sid = str(raw.get("id") or "").strip()
        jd_name = str(raw.get("name") or "").strip()
        if not sid and not jd_name:
            continue

        rid = sid if sid in skill_meta else name_to_id.get(jd_name.casefold())
        if not rid:
            unresolved.append(jd_name or sid)
            continue

        importance = _importance(raw)
        existing = resolved.get(rid)
        if existing is not None:
            if importance > existing["importance"]:
                existing["importance"] = importance
                existing["weight"] = importance
            continue

        meta = skill_meta[rid]
        graph_name = (meta.get("name") or jd_name).strip()
        row = {
            "skill_id": rid,
            "name": graph_name,
            "surface_form": _surface_form(raw, jd_name or graph_name),
            "skill_type": meta.get("skillType") or "",
            "importance": importance,
            "weight": importance,
            "min_years": _min_years(raw),
            "substitutable": _substitutable(raw),
            "evidence_sentence": _evidence_sentence(raw),
        }
        resolved[rid] = row
        order.append(rid)

    return [resolved[rid] for rid in order], unresolved


def _importance(raw: dict[str, Any]) -> float:
    """Read ``importance`` as a weight in ``[0, 1]``. Missing values weigh ``1.0``."""

    if "importance" not in raw or raw.get("importance") is None:
        return 1.0
    value = raw["importance"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    number = float(value)
    if not math.isfinite(number):
        return 1.0
    return min(1.0, max(0.0, number))


def _surface_form(raw: dict[str, Any], fallback: str) -> str:
    value = raw.get("surface_form")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _evidence_sentence(raw: dict[str, Any]) -> str:
    value = raw.get("evidence_sentence")
    if isinstance(value, str):
        return value
    return ""


def _substitutable(raw: dict[str, Any]) -> bool:
    value = raw.get("substitutable")
    return value if isinstance(value, bool) else False


def _min_years(raw: dict[str, Any]) -> int | None:
    value = raw.get("min_years")
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and math.isfinite(value) and value >= 0 and value.is_integer():
        return int(value)
    return None


def _requirements_text(sections: dict[str, Any]) -> str:
    """Read the requirements body from canonical sections, else the flat field."""

    canonical = sections.get("canonical") if isinstance(sections, dict) else None
    if isinstance(canonical, dict):
        entries = canonical.get("sections")
        if not isinstance(entries, list):
            return ""
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("section_type") or "") != _REQUIREMENTS_SECTION:
                continue
            return str(entry.get("content") or "").strip()
        return ""

    raw = sections.get(_REQUIREMENTS_SECTION) if isinstance(sections, dict) else None
    if isinstance(raw, str):
        return raw.strip()
    return ""

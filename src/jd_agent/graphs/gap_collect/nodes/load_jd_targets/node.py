"""Project the loaded JD's skills into raw gap-collector target rows."""

from __future__ import annotations

import math
from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.gap_collect.state import GapCollectState
from jd_agent.integrations.skills_graph import fetch_skills_by_ids
from jd_agent.integrations.supabase.jd_repository import JobDescription

_SKILL_FIELDS = ("id", "name", "skillType")


def load_jd_targets(state: GapCollectState, config: RunnableConfig) -> dict[str, Any]:
    """Build ``{id, name, skillType, requirement_level}`` rows for JD skill ids.

    ``id``, ``name``, and ``skillType`` come from the skills graph. The JD JSON
    is not a source for those fields. ``requirement_level`` is the JD skill's
    priority in ``[0, 1]`` (``1.0`` is required). Graph membership is resolved
    later in ``compute_gaps``.
    """
    _ = config
    jd = state.get("jd")
    if not isinstance(jd, JobDescription):
        raise ValueError("jd must be loaded before load_jd_targets")
    if not jd.skills:
        raise ValueError(f"job_description {jd.id} has no extracted skills; run jd_extract first")

    levels: dict[str, float] = {}
    ordered_ids: list[str] = []
    for skill in jd.skills:
        dumped = skill.model_dump()
        sid = str(dumped.get("id") or "").strip()
        if not sid:
            continue
        level = _requirement_level(dumped.get("importance"))
        if sid not in levels:
            ordered_ids.append(sid)
            levels[sid] = level
        elif level > levels[sid]:
            levels[sid] = level

    if not ordered_ids:
        raise ValueError(f"job_description {jd.id} skills have no ids; run jd_extract first")

    details = fetch_skills_by_ids(ordered_ids, fields=_SKILL_FIELDS)
    raw: list[dict[str, Any]] = []
    for sid in ordered_ids:
        row = details.get(sid) or {}
        raw.append(
            {
                "id": sid,
                "name": str(row.get("name") or "").strip(),
                "skillType": str(row.get("skillType") or "").strip(),
                "requirement_level": levels[sid],
            }
        )
    return {"jd_raw_skills": raw}


def _requirement_level(value: Any) -> float:
    """Read a priority in ``[0, 1]``. Missing or invalid values weigh ``1.0``."""

    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    number = float(value)
    if not math.isfinite(number):
        return 1.0
    return min(1.0, max(0.0, number))

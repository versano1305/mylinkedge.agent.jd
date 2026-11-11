"""Demand seed weights shared by JD extraction and resume scoring."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any


def demand_weight(skill: Any) -> float:
    """Read a positive seed weight. ``importance`` wins; else ``requirement_level``."""

    raw = _skill_record(skill)
    value = raw.get("importance")
    if value is None:
        value = raw.get("requirement_level", 1.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        return 0.0
    return min(1.0, number)


def demand_seeds(
    skills: Iterable[Any],
    *,
    known_ids: Iterable[str] | None = None,
) -> dict[str, float]:
    """Map resolved skill ids to demand weights.

    ``id`` wins; ``skill_id`` is accepted for rows that are already resolved
    (resume ``jd_targets``). Unresolved skills and non-positive weights are
    omitted. When the same id appears twice, the stronger weight is kept.
    ``known_ids`` drops ids that are not in the skill graph.
    """

    allowed = None if known_ids is None else set(known_ids)
    seeds: dict[str, float] = {}
    for skill in skills:
        raw = _skill_record(skill)
        skill_id = str(raw.get("id") or raw.get("skill_id") or "").strip()
        if not skill_id:
            continue
        if allowed is not None and skill_id not in allowed:
            continue
        weight = demand_weight(skill)
        if weight <= 0:
            continue
        current = seeds.get(skill_id)
        if current is None or weight > current:
            seeds[skill_id] = weight
    return seeds


def _skill_record(skill: Any) -> dict[str, Any]:
    if hasattr(skill, "model_dump"):
        raw = skill.model_dump()
        if isinstance(raw, dict):
            return raw
    if isinstance(skill, dict):
        return skill
    raise TypeError(f"skill must be a mapping or model, got {type(skill).__name__}")

"""Tier labels, line budgets, and promotion groups."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.constants import (
    TIER_A_RECENCY_YEARS,
    TIER_BUDGETS,
    TIER_D_AGE_YEARS,
)
from jd_agent.graphs.resume_generate.models import Instance
from jd_agent.graphs.resume_generate.nodes.allocate.work_instances import months_since_end


def _normalize_company(name: str) -> str:
    return " ".join(str(name or "").casefold().split())


def assign_tiers(
    instance_order: list[str],
    instances_by_id: dict[str, Instance],
    relevance: dict[str, float],
    atoms_by_exp: dict[str, list[dict[str, Any]]],
) -> dict[str, str]:
    """Assign A/B/C/D per plan defaults (user-approved product rules)."""

    tiers: dict[str, str] = {exp_id: "D" for exp_id in instance_order}

    eligible: list[tuple[str, float]] = []
    for exp_id in instance_order:
        inst = instances_by_id.get(exp_id)
        if inst is None:
            continue
        age_months = months_since_end(inst.end)
        if age_months is not None and age_months > TIER_D_AGE_YEARS * 12:
            continue
        if not atoms_by_exp.get(exp_id):
            continue
        if (relevance.get(exp_id) or 0.0) <= 0.0:
            continue
        eligible.append((exp_id, relevance[exp_id]))

    within_ten = []
    between_ten_fifteen = []
    for exp_id, rel in eligible:
        inst = instances_by_id[exp_id]
        age_months = months_since_end(inst.end)
        if age_months is not None and age_months <= TIER_A_RECENCY_YEARS * 12:
            within_ten.append((exp_id, rel))
        else:
            between_ten_fifteen.append((exp_id, rel))

    within_ten.sort(key=lambda x: (-x[1], x[0]))
    for idx, (exp_id, _) in enumerate(within_ten):
        if idx < 2:
            tiers[exp_id] = "A"
        elif idx == 2:
            tiers[exp_id] = "B"
        else:
            tiers[exp_id] = "C"

    for exp_id, _ in between_ten_fifteen:
        tiers[exp_id] = "C"

    return tiers


def promotion_groups(instance_order: list[str], instances_by_id: dict[str, Instance]) -> dict[str, list[str]]:
    """Consecutive roles at the same company (reverse-chronological order)."""

    groups: dict[str, list[str]] = {}
    current_key: str | None = None
    current_members: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_members
        if current_key and len(current_members) > 1:
            groups[current_key] = list(current_members)
        current_key = None
        current_members = []

    for exp_id in instance_order:
        inst = instances_by_id.get(exp_id)
        company = _normalize_company(inst.company if inst else "")
        if not company:
            flush()
            continue
        key = f"company:{company}"
        if key != current_key:
            flush()
            current_key = key
            current_members = [exp_id]
        else:
            current_members.append(exp_id)
    flush()
    return groups


def exp_promotion_group(
    exp_id: str, promotion_groups_map: dict[str, list[str]]
) -> frozenset[str]:
    for members in promotion_groups_map.values():
        if exp_id in members:
            return frozenset(members)
    return frozenset({exp_id})


def tier_budget_caps(tiers: dict[str, str]) -> dict[str, int]:
    """Per-experience tier line cap (trace / WU-08 reference)."""

    return {exp_id: TIER_BUDGETS.get(tier, 0) for exp_id, tier in tiers.items()}


def group_line_pools(
    tiers: dict[str, str],
    promotion_groups_map: dict[str, list[str]],
) -> dict[frozenset[str], int]:
    """Shared line pools for consecutive roles at one company."""

    caps = tier_budget_caps(tiers)
    pools: dict[frozenset[str], int] = {}
    for members in promotion_groups_map.values():
        pools[frozenset(members)] = sum(caps.get(m, 0) for m in members)
    return pools


def line_pool_for_exp(
    exp_id: str,
    tiers: dict[str, str],
    promotion_groups_map: dict[str, list[str]],
) -> int:
    caps = tier_budget_caps(tiers)
    group = exp_promotion_group(exp_id, promotion_groups_map)
    if len(group) > 1:
        return sum(caps.get(m, 0) for m in group)
    return caps.get(exp_id, 0)

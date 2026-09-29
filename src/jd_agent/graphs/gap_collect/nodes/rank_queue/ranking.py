"""Expected-yield ranking for the gap interview queue.

The interview is ranked by **expected yield, never by gap size**: a huge gap the
candidate almost certainly lacks is worth zero interview time; a medium gap they
probably have is worth everything.

    EV(v) = P(has v) · w(v) · gap(v)
    P(has v) ≈ σ(a·s*(v) + b·PPR_norm(v) − c)

The (a, b, c) constants below are **uncalibrated placeholders**. Per the
calibration playbook they should be fit by logistic loss on confirm/deny
outcomes before any user-visible number derived from ``p_has`` ships. They only
order the queue here; the interview answer, not the prior, establishes the fact.
"""

from __future__ import annotations

import math
from typing import Any

# Uncalibrated placeholder coefficients for P(has). See module docstring.
P_HAS_A = 3.5  # weight on supply-closure mastery s*
P_HAS_B = 1.5  # weight on normalized personalized PageRank
P_HAS_C = 1.0  # bias

DEFAULT_TARGET_QUESTIONS = 10
DEFAULT_MIN_EXPECTED_YIELD = 0.15


def _sigmoid(x: float) -> float:
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def p_has(s_star: float, ppr_norm: float) -> float:
    """Prior probability the candidate already has the skill."""
    return _sigmoid(P_HAS_A * s_star + P_HAS_B * ppr_norm - P_HAS_C)


def rank_candidates(
    candidates: list[dict[str, Any]],
    *,
    target_questions: int = DEFAULT_TARGET_QUESTIONS,
    min_expected_yield: float = DEFAULT_MIN_EXPECTED_YIELD,
) -> dict[str, Any]:
    """Score, sort, and bundle interview candidates into the queue block.

    Each candidate dict is expected to carry: ``skill_id``, ``skill_name``,
    ``skill_type``, ``zone``, ``latent_kind``, ``s_star``, ``ppr``, ``gap``,
    ``weight``, ``theme_id``, ``technique``, ``bridge_skill_ids``,
    ``bridge_skill_names``, ``prerequisite_names``, ``probe_hint``.
    """
    max_ppr = max((float(c.get("ppr") or 0.0) for c in candidates), default=0.0)

    queue: list[dict[str, Any]] = []
    for c in candidates:
        ppr_norm = (float(c.get("ppr") or 0.0) / max_ppr) if max_ppr > 0 else 0.0
        prob = p_has(float(c.get("s_star") or 0.0), ppr_norm)
        ev = prob * float(c.get("weight") or 1.0) * float(c.get("gap") or 0.0)
        skill_id = str(c.get("skill_id") or "")
        queue.append(
            {
                "round_id": f"skill::{skill_id}",
                "skill_id": skill_id,
                "skill_name": c.get("skill_name") or skill_id,
                "skill_type": c.get("skill_type") or "unknown",
                "zone": c.get("zone"),
                "latent_kind": c.get("latent_kind") or "",
                "expected_yield": round(ev, 6),
                "p_has": round(prob, 4),
                "technique": c.get("technique") or "open_recall",
                "bridge_skill_ids": list(c.get("bridge_skill_ids") or []),
                "bridge_skill_names": list(c.get("bridge_skill_names") or []),
                "prerequisite_names": list(c.get("prerequisite_names") or []),
                "theme_id": c.get("theme_id") or "",
                "probe_hint": c.get("probe_hint") or "",
            }
        )

    queue.sort(key=lambda r: r["expected_yield"], reverse=True)

    return {
        "queue": queue,
        "bundles": _build_bundles(queue),
        "stopping": {
            "target_questions": target_questions,
            "min_expected_yield": min_expected_yield,
        },
    }


def _build_bundles(queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group rounds by theme, preserving expected-yield order within a bundle."""
    order: list[str] = []
    by_theme: dict[str, list[str]] = {}
    for row in queue:
        theme_id = str(row.get("theme_id") or "")
        if not theme_id:
            continue
        if theme_id not in by_theme:
            by_theme[theme_id] = []
            order.append(theme_id)
        by_theme[theme_id].append(row["round_id"])
    return [{"theme_id": tid, "round_ids": by_theme[tid]} for tid in order]

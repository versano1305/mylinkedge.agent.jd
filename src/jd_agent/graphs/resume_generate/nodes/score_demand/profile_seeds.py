"""Profile-level supply seeds for demand scoring (WU-04)."""

from __future__ import annotations

from typing import Any

from jd_agent.shared.dossier_skills import instance_evidence_skill_ids


def profile_supply_seeds(
    dossier: dict[str, Any],
    *,
    has_skill_seed: float,
) -> tuple[dict[str, float], dict[str, float]]:
    """Return ``(s_seed, s_explicit)`` for supply closure and zone assignment.

    Instance evidence seeds at ``1.0`` with explicit confirmation. ``Person
    -HAS_SKILL->`` entries seed at ``has_skill_seed`` and remain implicit
    (``s_explicit`` 0).
    """

    evidence = instance_evidence_skill_ids(dossier)
    s_seed = {sid: 1.0 for sid in evidence}
    s_explicit = {sid: 1.0 for sid in evidence}

    for sk in dossier.get("skills") or []:
        if not isinstance(sk, dict):
            continue
        sid = str(sk.get("id") or "").strip()
        if not sid or sid in evidence:
            continue
        s_seed[sid] = has_skill_seed
        s_explicit.setdefault(sid, 0.0)

    return s_seed, s_explicit

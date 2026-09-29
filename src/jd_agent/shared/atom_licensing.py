"""Per-atom JD term licensing from supply closure (WU-06).

Uses the same ``LICENSE_TAU`` threshold semantics as allocation coverage:
one calibrated ontology hop may imply a JD term; ``PART_OF``-only paths do not.
"""

from __future__ import annotations

from typing import Any

from jd_agent.shared.gap_zones import ZONE_LATENT
from jd_agent.shared.skill_closures import DOMAIN_SKILL_TYPE


def _term_row(
    jd_skill_id: str,
    surface_form: str,
    via: str,
    s: float | None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "jd_skill_id": jd_skill_id,
        "surface_form": surface_form,
        "via": via,
    }
    if s is not None:
        row["s"] = round(float(s), 4)
    return row


def partition_demand_skill_terms(
    *,
    atom_skill_ids: set[str],
    s_star_atom: dict[str, float],
    d_star: dict[str, float],
    jd_rows_by_id: dict[str, dict[str, Any]],
    profile_zones: dict[str, str],
    profile_latent_kind: dict[str, str],
    license_tau: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split non-domain JD demand skills into licensed vs adjacent for one atom."""

    licensed: list[dict[str, Any]] = []
    adjacent: list[dict[str, Any]] = []
    seen_licensed: set[str] = set()
    seen_adjacent: set[str] = set()

    for jid, dv in d_star.items():
        if float(dv) <= 0:
            continue
        row = jd_rows_by_id.get(jid)
        if not row:
            continue
        if str(row.get("skill_type") or "") == DOMAIN_SKILL_TYPE:
            continue

        surface = str(row.get("surface_form") or row.get("name") or jid)
        supply = float(s_star_atom.get(jid, 0.0))

        if jid in atom_skill_ids:
            if jid not in seen_licensed:
                licensed.append(_term_row(jid, surface, "explicit", supply or None))
                seen_licensed.add(jid)
            continue

        if supply >= license_tau:
            if jid not in seen_licensed:
                licensed.append(_term_row(jid, surface, "implied", supply))
                seen_licensed.add(jid)
            continue

        profile_zone = str(profile_zones.get(jid) or "")
        if supply > 0.0 and supply < license_tau:
            if jid not in seen_adjacent and jid not in seen_licensed:
                adjacent.append(_term_row(jid, surface, "implied", supply))
                seen_adjacent.add(jid)
            continue

        if profile_zone == ZONE_LATENT:
            if jid not in seen_adjacent and jid not in seen_licensed:
                adjacent.append(
                    _term_row(
                        jid,
                        surface,
                        "implied",
                        supply if supply > 0 else None,
                    )
                )
                seen_adjacent.add(jid)

    return licensed, adjacent


def partition_domain_skill_terms(
    *,
    atom_skill_ids: set[str],
    instance_domain_ids: set[str],
    jd_domain_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Domain JD terms are licensed only when explicit on the atom or instance."""

    explicit = set(atom_skill_ids) | set(instance_domain_ids)
    licensed: list[dict[str, Any]] = []
    for row in jd_domain_rows:
        jid = str(row.get("skill_id") or "").strip()
        if not jid or jid not in explicit:
            continue
        surface = str(row.get("surface_form") or row.get("name") or jid)
        licensed.append(_term_row(jid, surface, "explicit", None))
    return licensed

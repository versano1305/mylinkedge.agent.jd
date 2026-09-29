"""Instance-level explicit Domain skills for JD domain licensing."""

from __future__ import annotations

from typing import Any


def _jd_domain_index(jd_domains: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("skill_id") or "").strip(): row
        for row in jd_domains
        if str(row.get("skill_id") or "").strip()
    }


def _name_matches_domain(label: str, row: dict[str, Any]) -> bool:
    folded = label.strip().casefold()
    if not folded:
        return False
    for key in ("name", "surface_form"):
        val = str(row.get(key) or "").strip().casefold()
        if val and val == folded:
            return True
    return False


def instance_domain_skill_ids(
    dossier: dict[str, Any],
    jd_domains: list[dict[str, Any]],
) -> dict[str, set[str]]:
    """Per ``instance_id``, Domain skill ids that may license JD domain terms."""

    domain_by_id = _jd_domain_index(jd_domains)
    if not domain_by_id:
        return {}

    out: dict[str, set[str]] = {}
    for inst in dossier.get("instances") or []:
        if not isinstance(inst, dict):
            continue
        iid = str(inst.get("instance_id") or "").strip()
        if not iid:
            continue
        ids: set[str] = set()
        for sk in inst.get("skills") or []:
            if not isinstance(sk, dict):
                continue
            if str(sk.get("skillType") or "") != "Domain":
                continue
            sid = str(sk.get("id") or "").strip()
            if sid in domain_by_id:
                ids.add(sid)
        industry = str(inst.get("industry") or "").strip()
        if industry:
            for jid, row in domain_by_id.items():
                if _name_matches_domain(industry, row):
                    ids.add(jid)
        if ids:
            out[iid] = ids
    return out

"""Person dossier skill id helpers (WU-04 / WU-08)."""

from __future__ import annotations

from typing import Any


def instance_evidence_skill_ids(dossier: dict[str, Any]) -> set[str]:
    """Skill ids from instance edges and certificate ``CERTIFIES_SKILL`` links."""

    ids: set[str] = set()
    for inst in dossier.get("instances") or []:
        if not isinstance(inst, dict):
            continue
        for sk in inst.get("skills") or []:
            if not isinstance(sk, dict):
                continue
            sid = str(sk.get("id") or "").strip()
            if sid:
                ids.add(sid)
    for cert in dossier.get("certificates") or []:
        if not isinstance(cert, dict):
            continue
        for sk in cert.get("skills") or []:
            if not isinstance(sk, dict):
                continue
            sid = str(sk.get("id") or "").strip()
            if sid:
                ids.add(sid)
    return ids

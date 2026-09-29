"""Gap report for JD skills the resume does not claim."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.nodes.verify.coverage import _compile


def build_gap_report(
    jd_targets: list[dict[str, Any]],
    demand: dict[str, Any],
    atoms: list[dict[str, Any]],
    resume_blob: str,
    covered_skill_ids: set[str],
) -> list[dict[str, Any]]:
    d_star = {
        k: float(v) for k, v in (demand.get("d_star") or {}).items()
    }
    zones = demand.get("zones") if isinstance(demand.get("zones"), dict) else {}
    entries: list[dict[str, Any]] = []

    adjacent_by_jd: dict[str, str] = {}
    for atom in atoms:
        if not isinstance(atom, dict):
            continue
        for adj in atom.get("adjacent") or []:
            if not isinstance(adj, dict):
                continue
            jid = str(adj.get("jd_skill_id") or "").strip()
            if not jid:
                continue
            via = str(adj.get("surface_form") or adj.get("name") or "").strip()
            if via:
                adjacent_by_jd.setdefault(jid, via)

    for target in jd_targets:
        if not isinstance(target, dict):
            continue
        sid = str(target.get("skill_id") or "").strip()
        if not sid or float(d_star.get(sid, 0.0)) <= 0:
            continue
        surface = str(target.get("surface_form") or target.get("name") or sid)
        pat = _compile(surface)
        if pat and pat.search(resume_blob):
            continue
        if sid in covered_skill_ids:
            continue

        zone = str(zones.get(sid) or "")
        substitutable = bool(target.get("substitutable"))
        min_years = target.get("min_years")

        if adjacent_by_jd.get(sid) or zone == "latent":
            via = adjacent_by_jd.get(sid, "")
            advice = (
                f"The JD accepts similar tools; {via} is named elsewhere."
                if substitutable and via
                else "Structurally adjacent skill not named on the resume."
            )
            entries.append(
                {
                    "skill_id": sid,
                    "name": surface,
                    "status": "adjacent",
                    "via": via or None,
                    "advice": advice,
                }
            )
            continue

        if min_years is not None:
            entries.append(
                {
                    "skill_id": sid,
                    "name": surface,
                    "status": "true_gap",
                    "via": None,
                    "advice": f"Qualifier requires {min_years}+ years; not claimed on resume.",
                }
            )
            continue

        if zone == "true_gap":
            entries.append(
                {
                    "skill_id": sid,
                    "name": surface,
                    "status": "true_gap",
                    "via": None,
                    "advice": "No evidence path to claim this JD skill on the resume.",
                }
            )

    return entries

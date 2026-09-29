"""Literal JD-term coverage of assembled resume text."""

from __future__ import annotations

import re
from typing import Any


def _importance_bucket(target: dict[str, Any]) -> str:
    imp = target.get("importance")
    if isinstance(imp, (int, float)) and float(imp) < 0.75:
        return "nice"
    return "must"


def _compile(span: str) -> re.Pattern[str] | None:
    cleaned = str(span).strip()
    if len(cleaned) < 2:
        return None
    return re.compile(rf"(?<![a-z0-9]){re.escape(cleaned)}(?![a-z0-9])", re.I)


def resume_text_blob(
    generated: dict[str, Any],
    summary_text: str,
    static_skills: list[dict[str, Any]],
) -> str:
    parts: list[str] = [summary_text]
    for payload in generated.values():
        if not isinstance(payload, dict):
            continue
        for row in payload.get("highlights") or []:
            if isinstance(row, dict):
                parts.append(str(row.get("text") or ""))
        parts.append(str(payload.get("summary") or ""))
    for group in static_skills:
        if not isinstance(group, dict):
            continue
        parts.append(str(group.get("name") or ""))
        for kw in group.get("keywords") or []:
            parts.append(str(kw))
    return "\n".join(p for p in parts if p)


def compute_coverage(
    jd_targets: list[dict[str, Any]],
    d_star: dict[str, float],
    resume_blob: str,
) -> dict[str, Any]:
    must_total = must_covered = nice_total = nice_covered = 0
    weighted_num = 0.0
    weighted_den = 0.0

    for target in jd_targets:
        if not isinstance(target, dict):
            continue
        sid = str(target.get("skill_id") or "").strip()
        if not sid or float(d_star.get(sid, 0.0)) <= 0:
            continue
        surface = str(target.get("surface_form") or target.get("name") or "").strip()
        if not surface:
            continue
        weight = float(target.get("weight") or 1.0)
        bucket = _importance_bucket(target)
        pat = _compile(surface)
        hit = bool(pat and pat.search(resume_blob))
        if bucket == "nice":
            nice_total += 1
            nice_covered += int(hit)
        else:
            must_total += 1
            must_covered += int(hit)
        weighted_den += weight
        if hit:
            weighted_num += weight

    weighted = weighted_num / weighted_den if weighted_den > 0 else 0.0
    return {
        "weighted": round(weighted, 4),
        "must": {"covered": must_covered, "total": must_total},
        "nice": {"covered": nice_covered, "total": nice_total},
    }

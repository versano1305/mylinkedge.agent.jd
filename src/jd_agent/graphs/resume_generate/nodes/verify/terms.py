"""JD skill span catalog for hidden-term scans."""

from __future__ import annotations

import re
from typing import Any


def _compile_span(span: str) -> re.Pattern[str] | None:
    cleaned = span.strip()
    if len(cleaned) < 2:
        return None
    return re.compile(rf"(?<![a-z0-9]){re.escape(cleaned)}(?![a-z0-9])", re.I)


def jd_spans_for_scan(
    jd_targets: list[dict[str, Any]],
    d_star: dict[str, float],
    skill_meta: dict[str, dict[str, str]],
) -> list[tuple[str, str, re.Pattern[str]]]:
    """Return (skill_id, label, pattern) for demand skills."""

    out: list[tuple[str, str, re.Pattern[str]]] = []
    seen: set[tuple[str, str]] = set()
    for target in jd_targets:
        if not isinstance(target, dict):
            continue
        sid = str(target.get("skill_id") or "").strip()
        if not sid or float(d_star.get(sid, 0.0)) <= 0:
            continue
        meta_name = str(skill_meta.get(sid, {}).get("name") or "").strip()
        for label in (
            str(target.get("surface_form") or "").strip(),
            str(target.get("name") or "").strip(),
            meta_name,
        ):
            if not label:
                continue
            key = (sid, label.casefold())
            if key in seen:
                continue
            pat = _compile_span(label)
            if pat is None:
                continue
            seen.add(key)
            out.append((sid, label, pat))
    return out


def find_hidden_terms(
    text: str,
    spans: list[tuple[str, str, re.Pattern[str]]],
    licensed: set[str],
) -> list[str]:
    """Return JD labels that appear in ``text`` but are not licensed."""

    violations: list[str] = []
    licensed_fold = {t.casefold() for t in licensed if t.strip()}
    for _sid, label, pat in spans:
        if label.casefold() in licensed_fold:
            continue
        if pat.search(text):
            violations.append(label)
    return violations

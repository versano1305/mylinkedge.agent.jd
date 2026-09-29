"""Uncalibrated atom strength (WU-05)."""

from __future__ import annotations

from datetime import date

from jd_agent.graphs.resume_generate.constants import RECENCY_MONTHS
from jd_agent.graphs.resume_generate.models import AtomKind


def age_months(end: str | None, *, today: date | None = None) -> int:
    """Months from ``end`` (YYYY-MM) to today; present/end missing → 0."""

    if not end:
        return 0
    parts = end.split("-")
    if len(parts) < 2:
        return 0
    try:
        y, m = int(parts[0]), int(parts[1])
    except ValueError:
        return 0
    ref = today or date.today()
    months = (ref.year - y) * 12 + (ref.month - m)
    return max(0, months)


def recency_factor(end: str | None, *, today: date | None = None) -> float:
    return max(0.5, pow(2.718281828, -age_months(end, today=today) / RECENCY_MONTHS))


def base_strength(kind: AtomKind, *, has_metric: bool, text_has_number: bool) -> float:
    if kind == "achievement":
        return 1.0 if has_metric else 0.85
    if kind == "project":
        return 0.75
    if kind == "mentorship":
        return 0.7
    if kind == "summary_sentence":
        return 0.7 if text_has_number else 0.6
    return 0.6


def compute_strength(
    kind: AtomKind,
    *,
    end: str | None,
    metrics: list[str],
    text: str,
    source_kinds: set[str],
    today: date | None = None,
) -> float:
    has_number = any(ch.isdigit() for ch in text)
    base = base_strength(
        kind,
        has_metric=bool(metrics),
        text_has_number=has_number,
    )
    interview_boost = 1.0
    if any(k.casefold() == "interview" for k in source_kinds):
        interview_boost = 1.1
    return round(base * recency_factor(end, today=today) * interview_boost, 4)

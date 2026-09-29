"""In-node validation for generated ``basics.summary``."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.constants import BASICS_SUMMARY_MAX_WORDS
from jd_agent.graphs.resume_generate.models import SummaryResult
from jd_agent.shared.resume_metrics import extract_metrics
from jd_agent.shared.resume_text import contains_first_person, word_count


def validate_summary(
    context: dict[str, Any],
    result: SummaryResult,
) -> list[str]:
    errors: list[str] = []
    text = result.text.strip()
    if not text:
        errors.append("summary text is empty")
        return errors

    if word_count(text) > BASICS_SUMMARY_MAX_WORDS:
        errors.append(
            f"summary exceeds {BASICS_SUMMARY_MAX_WORDS} words ({word_count(text)})"
        )
    if contains_first_person(text):
        errors.append("summary must not use first person")

    allowed_terms = set(context.get("allowed_terms") or [])
    for term in result.claimed_terms:
        t = str(term).strip()
        if t and t not in allowed_terms:
            errors.append(f"claimed term {t!r} not in allowed_terms")

    allowed_numbers = set(context.get("allowed_numbers") or [])
    for num in result.claimed_numbers:
        n = str(num).strip()
        if n and n not in allowed_numbers:
            errors.append(f"claimed number {n!r} not in allowed_numbers")

    flagship = context.get("flagship_metric")
    if isinstance(flagship, dict):
        metric = str(flagship.get("metric") or "").strip()
        if metric and metric not in text:
            errors.append(f"summary must include flagship metric {metric!r} verbatim")

    for span in extract_metrics(text):
        if span not in allowed_numbers:
            errors.append(f"number {span!r} in text is not allowed")

    return errors

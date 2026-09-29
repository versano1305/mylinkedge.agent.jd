"""Prompt templates for ``basics.summary`` generation."""

from __future__ import annotations

import json
from typing import Any

from jd_agent.graphs.resume_generate.constants import BASICS_SUMMARY_MAX_WORDS

DEFAULT_SYSTEM_PROMPT = f"""You write the professional summary (basics.summary) for a resume.

Rules:
- Write 2–4 sentences, at most {BASICS_SUMMARY_MAX_WORDS} words. No first person.
- Open with the candidate label and target role context; do not invent titles.
- State total career years only using total_years_display (never invent years).
- Per-skill years only for per_skill_qualified; never mention per_skill_omit skills.
- Include exactly one flagship metric, verbatim from flagship_metric.metric when set.
- Name JD terms only from allowed_terms (already on the resume).
- You may reference skill_group_labels as themes.
- Fill claimed_terms and claimed_numbers with every JD term and number you use.
"""


def build_user_message(
    context: dict[str, Any],
    *,
    validation_errors: list[str] | None = None,
    repair_feedback: list[str] | None = None,
) -> str:
    sections = [json.dumps(context, indent=2)]
    if repair_feedback:
        sections.append(
            "Repair feedback from verification (fix these issues):\n"
            + "\n".join(f"- {line}" for line in repair_feedback)
        )
    if validation_errors:
        sections.append(
            "Your previous answer failed validation. Fix every issue:\n"
            + "\n".join(f"- {line}" for line in validation_errors)
        )
    return "\n\n".join(sections)

"""Prompt templates for resume highlight generation."""

from __future__ import annotations

import json

from jd_agent.graphs.resume_generate.constants import (
    HIGHLIGHT_MAX_WORDS,
    SUMMARY_MAX_WORDS,
)
from jd_agent.graphs.resume_generate.models import InstanceBrief

DEFAULT_SYSTEM_PROMPT = f"""You rewrite evidence atoms into resume bullets for one role.

Rules:
- Produce exactly the requested number of bullets. Each bullet uses 1–2 listed atoms only.
- Use listed JD TERMS verbatim when the atom supports them. Do not name other tools, technologies, clients, or scope.
- Keep every number exactly as given in the atoms. Do not add numbers.
- Start each bullet with a strong verb. Use past tense for past roles and present tense for current roles. No first person.
- Each bullet must be at most {HIGHLIGHT_MAX_WORDS} words. No two bullets may start with the same verb.
- When a metric exists, order as action, scope, then result.
- Optional one-line role summary: at most {SUMMARY_MAX_WORDS} words, using only industry, company description, and team size from the header.
- Fill atom_ids and jd_terms_used on every highlight so they match what you wrote.
"""


def build_user_message(
    brief: InstanceBrief,
    *,
    validation_errors: list[str] | None = None,
    repair_feedback: list[str] | None = None,
) -> str:
    """Serialize the instance brief and optional retry / repair hints."""
    payload = {
        "header": {
            "company": brief.company,
            "position": brief.position,
            "startDate": brief.startDate,
            "endDate": brief.endDate,
            "location": brief.location,
            "employmentType": brief.employmentType,
            "teamSize": brief.teamSize,
            "industry": brief.industry,
            "company_description": brief.company_description,
        },
        "tense": brief.tense,
        "budget": brief.budget,
        "atoms": [
            {
                "atom_id": atom.atom_id,
                "text": atom.text,
                "metrics": atom.metrics,
                "jd_terms": atom.licensed,
            }
            for atom in brief.atoms
        ],
    }
    sections = [json.dumps(payload, indent=2)]
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

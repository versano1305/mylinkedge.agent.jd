"""Uncalibrated tuning defaults for resume generation.

Numeric and template defaults only. Neo4j labels and relationship types live
in ``taxonomy_types`` and are never copied here.
"""

from __future__ import annotations

from typing import Any

LICENSE_TAU = 0.80
HAS_SKILL_SEED = 0.50
CONTEXT_SEED = 0.50
MIN_GAIN = 0.01
MAX_HIGHLIGHTS_ONE_PAGE = 10
MAX_HIGHLIGHTS_TWO_PAGES = 18
TIER_BUDGETS: dict[str, int] = {"A": 5, "B": 3, "C": 1, "D": 0}
RECENCY_MONTHS = 60
TIER_A_RECENCY_YEARS = 10
TIER_D_AGE_YEARS = 15
TITLE_SIMILARITY_LAMBDA = 0.3
MAX_SKILL_GROUPS = 5
MAX_KEYWORDS_PER_GROUP = 8
N_EXTRA_SKILLS = 6
MAX_REPAIR_ROUNDS = 2
HIGHLIGHT_MAX_WORDS = 30
SUMMARY_MAX_WORDS = 20
BASICS_SUMMARY_MAX_WORDS = 60
BASICS_SUMMARY_IN_NODE_RETRIES = 1
HIGHLIGHT_LLM_TEMPERATURE = 0.2
BASICS_SUMMARY_LLM_TEMPERATURE = 0.2
# Extra LLM attempts after the first (validation-driven in-node retry).
HIGHLIGHT_IN_NODE_RETRIES = 1

DEFAULT_TEMPLATE: dict[str, Any] = {
    "page_budget": 2,
    "section_order": [
        "basics",
        "work",
        "education",
        "certificates",
        "skills",
        "projects",
        "languages",
    ],
    "max_highlights_total": MAX_HIGHLIGHTS_TWO_PAGES,
    "include_projects": True,
}


def trace_constants() -> dict[str, Any]:
    """Snapshot echoed into ``trace.meta.constants``."""

    return {
        "license_tau": LICENSE_TAU,
        "has_skill_seed": HAS_SKILL_SEED,
        "context_seed": CONTEXT_SEED,
        "min_gain": MIN_GAIN,
        "max_highlights_one_page": MAX_HIGHLIGHTS_ONE_PAGE,
        "max_highlights_two_pages": MAX_HIGHLIGHTS_TWO_PAGES,
        "tier_budgets": dict(TIER_BUDGETS),
        "recency_months": RECENCY_MONTHS,
        "tier_a_recency_years": TIER_A_RECENCY_YEARS,
        "tier_d_age_years": TIER_D_AGE_YEARS,
        "title_similarity_lambda": TITLE_SIMILARITY_LAMBDA,
        "max_skill_groups": MAX_SKILL_GROUPS,
        "max_keywords_per_group": MAX_KEYWORDS_PER_GROUP,
        "n_extra_skills": N_EXTRA_SKILLS,
        "max_repair_rounds": MAX_REPAIR_ROUNDS,
        "highlight_max_words": HIGHLIGHT_MAX_WORDS,
        "summary_max_words": SUMMARY_MAX_WORDS,
        "basics_summary_max_words": BASICS_SUMMARY_MAX_WORDS,
        "basics_summary_in_node_retries": BASICS_SUMMARY_IN_NODE_RETRIES,
        "highlight_in_node_retries": HIGHLIGHT_IN_NODE_RETRIES,
    }

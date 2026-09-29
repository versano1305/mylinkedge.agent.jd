"""Backward-compatible re-exports; canonical code lives in ``jd_agent.shared``."""

from jd_agent.shared.gap_zones import (  # noqa: F401
    DEFAULT_WEIGHT,
    GAP_P,
    LATENT_DELTA,
    PPR_PERCENTILE,
    ZONE_CONFIRMED,
    ZONE_LATENT,
    ZONE_TRUE_GAP,
    SkillMeta,
    assign_zone,
    build_themes,
    compute_gaps,
    critical_path,
    fit_if_latent_skills_confirmed,
    personalized_pagerank,
)

__all__ = [
    "DEFAULT_WEIGHT",
    "GAP_P",
    "LATENT_DELTA",
    "PPR_PERCENTILE",
    "ZONE_CONFIRMED",
    "ZONE_LATENT",
    "ZONE_TRUE_GAP",
    "SkillMeta",
    "assign_zone",
    "build_themes",
    "compute_gaps",
    "critical_path",
    "fit_if_latent_skills_confirmed",
    "personalized_pagerank",
]

"""Display strings for years-of-experience claims (WU-10 / WU-11)."""

from __future__ import annotations

import math


def format_career_years(total_years: float) -> str:
    """Resume-style total experience (e.g. ``12+``)."""

    if total_years <= 0 or not math.isfinite(total_years):
        return ""
    whole = max(1, int(total_years))
    return f"{whole}+"


def format_skill_years(union_years: float) -> str:
    """Whole years for a per-skill qualifier that met ``min_years``."""

    if union_years <= 0 or not math.isfinite(union_years):
        return ""
    whole = max(1, int(round(union_years)))
    return str(whole)


def career_year_allowlist(total_years: float) -> set[str]:
    """Allowed numeric tokens for total career years in summary text."""

    display = format_career_years(total_years)
    if not display:
        return set()
    whole = display.rstrip("+")
    allowed = {display, whole, f"{whole}+", f"{whole} years", f"{whole}+ years"}
    return {a.strip() for a in allowed if a.strip()}


def skill_year_allowlist(union_years: float) -> set[str]:
    display = format_skill_years(union_years)
    if not display:
        return set()
    return {display, f"{display} years", f"{display}+", f"{display}+ years"}

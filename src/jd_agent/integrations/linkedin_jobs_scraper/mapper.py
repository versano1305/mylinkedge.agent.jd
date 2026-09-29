"""Map Bright Data LinkedIn Jobs scrape items to ``JobPosting``."""

from __future__ import annotations

from typing import Any

from jd_agent.shared.schemas import JobPosting


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def map_brightdata_item_to_job_posting(
    item: dict[str, Any],
    *,
    url: str,
    source: str = "linkedin",
) -> JobPosting:
    """Convert one Bright Data dataset item into a generic ``JobPosting``.

    Raises
    ------
    ValueError
        If ``job_summary`` is missing or empty.
    """
    summary = item.get("job_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(
            "Bright Data LinkedIn Jobs result is missing a non-empty job_summary."
        )

    return JobPosting(
        url=_optional_str(item.get("url")) or url,
        description=summary.strip(),
        title=_optional_str(item.get("job_title")),
        company_name=_optional_str(item.get("company_name")),
        location=_optional_str(item.get("job_location")),
        source=source,
    )

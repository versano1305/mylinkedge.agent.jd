"""Map parsed JD sections to Supabase ``job_description.sections`` jsonb.

Section text is stored once, under ``canonical``. The four legacy field names
(``description``, ``requirements``, ``responsibilities``, ``location``) are a
projection of that parse via each config row's ``legacy_target``.
"""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.jd_extract.nodes.save_jd_sections.models import (
    JDSectionParseResult,
    SectionConfig,
)
from jd_agent.graphs.jd_extract.state import JdExtractState

_LOCATION_HINTS = (
    "remote",
    "hybrid",
    "onsite",
    "on-site",
    "location",
    "based in",
    "work from",
    "office",
)

_LEGACY_FIELDS = (
    "description",
    "requirements",
    "responsibilities",
    "location",
)


def _extract_location_lines(text: str) -> str:
    """Return lines that look like location / work-model hints."""
    if not text:
        return ""
    matched: list[str] = []
    for line in text.splitlines():
        lowered = line.casefold()
        if any(hint in lowered for hint in _LOCATION_HINTS):
            matched.append(line.strip())
    return "\n".join(matched)


def _content_by_type(canonical: dict[str, Any]) -> dict[str, str]:
    raw = canonical.get("sections")
    if not isinstance(raw, list):
        return {}
    by_type: dict[str, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        section_type = str(entry.get("section_type") or "").strip()
        if not section_type:
            continue
        by_type[section_type] = str(entry.get("content") or "")
    return by_type


def legacy_sections(
    canonical: dict[str, Any],
    section_configs: list[SectionConfig],
) -> dict[str, str]:
    """Project ``canonical`` onto the legacy flat section fields.

    Content is grouped by ``legacy_target`` (or the section key when that is
    unset), in config sort order, and joined with a blank line. ``location``
    keeps only location-like lines when any match.
    """
    by_type = _content_by_type(canonical)
    buckets: dict[str, list[str]] = {}
    for cfg in section_configs:
        content = (by_type.get(cfg.key) or "").strip()
        target = (cfg.legacy_target or cfg.key).strip()
        if not target:
            continue
        buckets.setdefault(target, [])
        if content:
            buckets[target].append(content)

    def joined(target: str) -> str:
        return "\n\n".join(buckets.get(target) or [])

    location_raw = joined("location")
    projected = {field: joined(field) for field in _LEGACY_FIELDS}
    projected["location"] = _extract_location_lines(location_raw) or location_raw
    return projected


def to_supabase_sections(
    parsed: JDSectionParseResult,
    state: JdExtractState,
) -> dict[str, Any]:
    """Build the sections payload for ``upsert_sections``.

    Stores the parser output under ``canonical`` and copies ``title`` from the
    JD row so the upsert can sync ``title_name``.
    """
    jd = state.get("jd")
    title = ""
    if jd is not None:
        title = str(getattr(jd, "title_name", "") or "").strip()
    return {
        "title": title,
        "canonical": parsed.model_dump(mode="json"),
    }

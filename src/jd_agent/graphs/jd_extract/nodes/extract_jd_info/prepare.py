"""Build section work items from DB sections + enabled prompt configs."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.jd_extract.nodes.extract_jd_info.models import SectionWorkItem
from jd_agent.integrations.supabase.prompt_config_repository import (
    PROCESS_META_KEYS,
    PromptConfigRow,
    section_rows,
)


def _canonical_content(sections: dict[str, Any], key: str) -> str | None:
    """Return the canonical body for ``key``, or ``None`` when canonical is absent."""
    canonical = sections.get("canonical")
    if not isinstance(canonical, dict):
        return None
    canonical_sections = canonical.get("sections")
    if not isinstance(canonical_sections, list):
        return ""
    for entry in canonical_sections:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("section_type") or "") != key:
            continue
        return str(entry.get("content") or "").strip()
    return ""


def section_content_for_key(sections: dict[str, Any], key: str) -> str:
    """Resolve section body text for a config key from ``job_description.sections``.

    Uses the matching ``canonical.sections`` entry when ``canonical`` is present.
    Rows written before that shape fall back to the flat string at ``sections[key]``.
    """
    canonical_content = _canonical_content(sections, key)
    if canonical_content is not None:
        return canonical_content

    raw = sections.get(key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return ""


def build_section_work_items(
    sections: dict[str, Any],
    config_rows: list[PromptConfigRow],
) -> list[SectionWorkItem]:
    """Pair enabled section configs with matching JD section content.

    Skips process-meta keys and rows whose section content is empty/missing.
    """
    items: list[SectionWorkItem] = []
    for row in section_rows(config_rows):
        if row.key in PROCESS_META_KEYS:
            continue
        content = section_content_for_key(sections, row.key)
        if not content:
            continue
        items.append(
            SectionWorkItem(
                section_key=row.key,
                section_content=content,
                prompt_config={
                    "id": row.id,
                    "type": row.type,
                    "key": row.key,
                    "data": row.data if isinstance(row.data, dict) else {},
                    "sort_order": row.sort_order,
                    "enabled": row.enabled,
                },
                sort_order=row.sort_order,
            )
        )
    return items

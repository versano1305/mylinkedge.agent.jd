"""Unit tests for JD skills section work-item preparation."""

from __future__ import annotations

from jd_agent.graphs.jd_extract.nodes.extract_jd_info.prepare import (
    build_section_work_items,
    section_content_for_key,
)
from jd_agent.integrations.supabase.prompt_config_repository import PromptConfigRow


def _row(key: str, *, sort_order: int = 0, enabled: bool = True) -> PromptConfigRow:
    return PromptConfigRow(
        id=f"id-{key}",
        type="jd_section_extraction",
        key=key,
        data={"heading": key.title()},
        sort_order=sort_order,
        enabled=enabled,
    )


def test_section_content_prefers_canonical_over_flat() -> None:
    sections = {
        "requirements": "Must know Python",
        "canonical": {
            "sections": [
                {"section_type": "requirements", "content": "canonical only"},
            ]
        },
    }
    assert section_content_for_key(sections, "requirements") == "canonical only"


def test_section_content_ignores_flat_when_canonical_lacks_key() -> None:
    sections = {
        "description": "Folded overview",
        "canonical": {
            "sections": [
                {"section_type": "role_overview", "content": "Overview"},
            ]
        },
    }
    assert section_content_for_key(sections, "description") == ""
    assert section_content_for_key(sections, "role_overview") == "Overview"


def test_section_content_falls_back_to_flat_without_canonical() -> None:
    sections = {"requirements": "Must know Python"}
    assert section_content_for_key(sections, "requirements") == "Must know Python"


def test_section_content_falls_back_to_canonical() -> None:
    sections = {
        "canonical": {
            "sections": [
                {
                    "section_type": "responsibilities",
                    "content": "Own the roadmap",
                }
            ]
        }
    }
    assert (
        section_content_for_key(sections, "responsibilities") == "Own the roadmap"
    )


def test_build_section_work_items_pairs_enabled_section_rows() -> None:
    sections = {
        "description": "We build things",
        "requirements": "Python experience",
        "responsibilities": "",
    }
    rows = [
        _row("system_prompt", sort_order=0),
        _row("description", sort_order=1),
        _row("requirements", sort_order=2),
        _row("responsibilities", sort_order=3),
        _row("parse_rules", sort_order=4),
    ]

    items = build_section_work_items(sections, rows)

    assert [item.section_key for item in items] == ["description", "requirements"]
    assert items[0].section_content == "We build things"
    assert items[1].prompt_config["key"] == "requirements"
    assert items[1].prompt_config["data"]["heading"] == "Requirements"


def test_build_section_work_items_skips_missing_sections() -> None:
    sections = {"description": "Hello"}
    rows = [_row("description"), _row("location")]

    items = build_section_work_items(sections, rows)

    assert len(items) == 1
    assert items[0].section_key == "description"

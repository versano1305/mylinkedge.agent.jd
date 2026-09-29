"""Unit tests for JD section persistence mapping."""

from __future__ import annotations

from jd_agent.graphs.jd_extract.nodes.save_jd_sections.mapping import (
    legacy_sections,
    to_supabase_sections,
)
from jd_agent.graphs.jd_extract.nodes.save_jd_sections.models import (
    JDSectionParseResult,
    ParsedJDSection,
    SectionConfig,
)
from jd_agent.integrations.supabase.jd_repository import JobDescription


def _cfg(key: str, legacy_target: str | None = None) -> SectionConfig:
    return SectionConfig(key=key, legacy_target=legacy_target)


def test_to_supabase_sections_stores_canonical_only() -> None:
    parsed = JDSectionParseResult(
        sections=[
            ParsedJDSection(
                section_type="role_overview",
                heading="Role Overview",
                content="We build banking software.",
            ),
            ParsedJDSection(
                section_type="requirements",
                heading="Requirements",
                content="8+ years.",
            ),
        ]
    )
    state = {
        "jd": JobDescription(id="jd-1", title_name="Software Architect"),
    }

    sections = to_supabase_sections(parsed, state)

    assert set(sections) == {"title", "canonical"}
    assert sections["title"] == "Software Architect"
    assert sections["canonical"]["sections"][0]["section_type"] == "role_overview"
    assert sections["canonical"]["sections"][0]["content"] == "We build banking software."


def test_legacy_sections_folds_by_target_and_filters_location() -> None:
    canonical = {
        "sections": [
            {
                "section_type": "role_overview",
                "heading": "Role Overview",
                "content": "We build banking software.",
            },
            {
                "section_type": "requirements",
                "heading": "Requirements",
                "content": "8+ years.",
            },
            {
                "section_type": "benefits_perks",
                "heading": "Benefits",
                "content": "Health insurance\nRemote-friendly office in Tel Aviv",
            },
            {
                "section_type": "about_company",
                "heading": "About",
                "content": "Offices worldwide.",
            },
        ]
    }
    configs = [
        _cfg("role_overview", "description"),
        _cfg("about_company", "description"),
        _cfg("requirements"),
        _cfg("benefits_perks", "location"),
    ]

    projected = legacy_sections(canonical, configs)

    assert projected["description"] == "We build banking software.\n\nOffices worldwide."
    assert projected["requirements"] == "8+ years."
    assert projected["responsibilities"] == ""
    assert projected["location"] == "Remote-friendly office in Tel Aviv"

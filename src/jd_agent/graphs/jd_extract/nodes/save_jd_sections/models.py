"""Pydantic models for JD section parsing (config-driven section types)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from jd_agent.integrations.supabase.prompt_config_repository import (
    JD_SECTION_EXTRACTION,
)

__all__ = [
    "JD_SECTION_EXTRACTION",
    "JDSectionParseResult",
    "ParsedJDSection",
    "SectionConfig",
    "section_config_from_row",
]


class ParsedJDSection(BaseModel):
    """One canonical JD section produced by the section-parsing agent."""

    section_type: str = Field(
        description="Section identifier matching an agent_prompt_config key.",
    )
    heading: str = Field(
        default="",
        description="Primary source heading for this block.",
    )
    content: str = Field(
        default="",
        description="Verbatim source text re-organised under this section.",
    )


class JDSectionParseResult(BaseModel):
    """Structured response from the JD section parser agent."""

    sections: list[ParsedJDSection] = Field(
        default_factory=list,
        description="JD sections in config-defined order.",
    )


class SectionConfig(BaseModel):
    """View model for a section partition row from agent_prompt_config."""

    key: str
    heading: str = ""
    section_description: str = ""
    typical_content: str = ""
    legacy_target: str | None = None
    sort_order: int = 0


def section_config_from_row(
    *,
    key: str,
    data: dict,
    sort_order: int = 0,
) -> SectionConfig:
    """Build ``SectionConfig`` from a config table ``data`` jsonb payload."""
    legacy = data.get("legacy_target")
    return SectionConfig(
        key=key,
        heading=str(data.get("heading") or ""),
        section_description=str(data.get("section_description") or ""),
        typical_content=str(data.get("typical_content") or ""),
        legacy_target=str(legacy) if legacy else None,
        sort_order=sort_order,
    )

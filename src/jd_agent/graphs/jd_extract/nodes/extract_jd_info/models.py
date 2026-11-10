"""Contracts for the JD skills map-reduce subflow."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SectionWorkItem(BaseModel):
    """One section paired with its ``agent_prompt_config`` row."""

    section_key: str
    section_content: str
    prompt_config: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0


class SectionSkillResult(BaseModel):
    """Skill payload for one JD section after hub ``extract_skills`` results."""

    section_key: str
    skills: list[dict[str, Any]] = Field(default_factory=list)


class SectionSkillExtractionRef(BaseModel):
    """Published ``extract_skills`` event for one section."""

    section_key: str
    event_id: str

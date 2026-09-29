"""Contracts for the JD skills map-reduce subflow."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class SectionWorkItem(BaseModel):
    """One section paired with its ``agent_prompt_config`` row for fan-out."""

    section_key: str
    section_content: str
    prompt_config: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0


class SectionSkillResult(BaseModel):
    """Skill payload produced by one section's map branch."""

    section_key: str
    skills: list[dict[str, Any]] = Field(default_factory=list)


class SectionSkillWorkerState(TypedDict, total=False):
    """Isolated state for one section skill extraction."""

    section_task: dict[str, Any]
    section_skill_results: list[dict[str, Any]]

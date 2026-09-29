"""LLM contracts for highlight generation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from jd_agent.graphs.resume_generate.models import GeneratedHighlight


class HighlightGenerationResult(BaseModel):
    """Structured response for one instance's bullets and optional summary."""

    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    highlights: list[GeneratedHighlight] = Field(default_factory=list)

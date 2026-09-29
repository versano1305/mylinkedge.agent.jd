"""Pydantic models for JD graph inputs and outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    """Vendor-agnostic job posting returned by ``fetch_job_posting``.

    Provider-specific payloads (Bright Data, Greenhouse, …) map into this
    shape so the graph and tools stay independent of the retrieval API.
    """

    url: str
    description: str = Field(description="Plain-text job description body")
    title: str | None = None
    company_name: str | None = None
    location: str | None = None
    source: str | None = None


class JdExtractInput(BaseModel):
    """Studio / API input for the JD extraction graph.

    The row must already exist in ``job_description``; the graph loads
    origin fields from the database via ``jd_id``.
    """

    jd_id: str = Field(description="Existing job_description.id to process")


class JdExtractionNode(BaseModel):
    """One resolved requirement node from a JD extraction."""

    # TODO: align fields with downstream consumers (resume-generate, interview).
    id: str = ""
    label: str = ""
    original_label: str = ""
    node_type: str = ""
    priority: float = Field(default=0.0, ge=0.0, le=1.0)
    priority_text: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)


class JdExtraction(BaseModel):
    """Structured JD extraction produced by the parse_jd node."""

    # TODO: add persistence fields (id, owner_user_id, metadata) when saving.
    title: str = ""
    original_title: str = ""
    original_jd: str = ""
    nodes: list[JdExtractionNode] = Field(default_factory=list)

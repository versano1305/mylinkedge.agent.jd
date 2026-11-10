"""State schema for the JD extraction graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from jd_agent.integrations.supabase.jd_repository import JobDescription

JdExtractStatus = Literal["extracting", "done", "failed"]


def _replace_list(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    """Reducer that replaces the list when a non-None update is provided."""
    if right is None:
        return list(left or [])
    return list(right)


class JdExtractState(TypedDict, total=False):
    """Shared state that flows through JD extraction nodes.

    The unprocessed JD record already exists in the database before the
    graph is invoked. Callers pass that row as ``jd``. ``initialize``
    validates it; source fields (origin_jd, origin_type, company_name, …)
    are read from ``jd``.

    Skills are persisted by ``save_jd_skills`` and are not mirrored in a
    separate ``extraction`` blob. ``resolve_company`` publishes a company
    lookup; ``company_id`` is filled downstream.
    """

    # Studio / API input. ``jd`` is the existing row; ``jd_id`` mirrors ``jd.id``.
    jd_id: str
    jd: JobDescription

    # Intermediate
    jd_text: str  # Normalized plain-text JD after fetch or copy-paste
    jd_sections: dict[str, Any]  # Serialized JDSectionParseResult after save_jd_sections
    jd_demands: dict[str, Any]  # Demand closure after compute_demands

    # Skills subflow (enriched before save_jd_skills, then cleared)
    section_tasks: Annotated[list[dict[str, Any]], _replace_list]
    # Published ``extract_skills`` event refs for ``collect_section_skill_results``
    section_skill_extractions: Annotated[list[dict[str, Any]], _replace_list]
    section_skill_results: Annotated[list[dict[str, Any]], operator.add]

    # Output
    company_id: str  # Filled downstream from COMPANY_LOOKUP
    extraction_status: JdExtractStatus  # extracting → done, or failed on error

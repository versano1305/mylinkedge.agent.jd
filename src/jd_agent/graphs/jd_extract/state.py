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

    ``jd_id`` is required: the unprocessed JD record already exists in the
    database before the graph is invoked. ``load_jd`` hydrates ``jd`` from
    that row; source fields (origin_jd, origin_type, company_name, …) are
    read from ``jd`` rather than duplicated as invoke inputs.

    Skills are persisted by ``save_jd_skills`` and are not mirrored in a
    separate ``extraction`` blob. Company fields are persisted by
    ``resolve_company``.
    """

    # Studio / API input
    jd_id: str  # Required: existing JD record being processed

    # Loaded from DB
    jd: JobDescription

    # Intermediate
    jd_text: str  # Normalized plain-text JD after fetch or copy-paste
    jd_sections: dict[str, Any]  # Serialized JDSectionParseResult after save_jd_sections

    # Skills map-reduce (enriched before save_jd_skills, then cleared)
    section_tasks: Annotated[list[dict[str, Any]], _replace_list]
    section_skill_results: Annotated[list[dict[str, Any]], operator.add]

    # Output
    company_id: str  # Resolved existing company DB record ID
    extraction_status: JdExtractStatus  # extracting → done, or failed on error

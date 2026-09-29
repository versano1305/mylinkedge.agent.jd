"""Repository for public.agent_prompt_config (Supabase / PostgREST)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from supabase import Client

AGENT_PROMPT_CONFIG_TABLE = "agent_prompt_config"

# Process-level keys that are not section partitions.
PROCESS_META_KEYS = frozenset({"system_prompt", "parse_rules", "user_prompt"})

JD_SECTION_EXTRACTION = "jd_section_extraction"
JD_SECTION_SKILL_EXTRACTION = "jd_section_skill_extraction"


class PromptConfigRow(BaseModel):
    """One row from ``agent_prompt_config``."""

    id: str = ""
    type: str
    key: str
    data: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0
    enabled: bool = True


def _raise_on_error(error: Any, *, fallback: str) -> None:
    if error is None:
        return
    message = getattr(error, "message", None) or str(error) or fallback
    raise RuntimeError(message)


def list_by_type(
    client: Client,
    process_type: str,
    *,
    enabled_only: bool = True,
) -> list[PromptConfigRow]:
    """Load config rows for a process type, ordered by ``sort_order``."""
    query = (
        client.table(AGENT_PROMPT_CONFIG_TABLE)
        .select("id, type, key, data, sort_order, enabled")
        .eq("type", process_type)
        .order("sort_order")
    )
    if enabled_only:
        query = query.eq("enabled", True)

    response = query.execute()
    _raise_on_error(
        getattr(response, "error", None),
        fallback=f"Failed to load agent_prompt_config for type={process_type}",
    )
    rows = response.data or []
    if not isinstance(rows, list):
        rows = [rows]
    return [PromptConfigRow.model_validate(row) for row in rows]


def section_rows(rows: list[PromptConfigRow]) -> list[PromptConfigRow]:
    """Filter out process-meta keys; keep section partition rows."""
    return [row for row in rows if row.key not in PROCESS_META_KEYS]


def get_row_by_key(
    rows: list[PromptConfigRow],
    key: str,
) -> PromptConfigRow | None:
    """Return the first row with the given ``key``, or ``None``."""
    for row in rows:
        if row.key == key:
            return row
    return None

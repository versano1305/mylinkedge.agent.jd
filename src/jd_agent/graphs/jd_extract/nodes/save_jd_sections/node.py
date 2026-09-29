"""LangGraph node: partition ``jd_text`` into sections and persist them."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.jd_extract.nodes.save_jd_sections.agent import invoke_section_parser
from jd_agent.graphs.jd_extract.nodes.save_jd_sections.mapping import (
    to_supabase_sections,
)
from jd_agent.graphs.jd_extract.nodes.save_jd_sections.models import (
    JD_SECTION_EXTRACTION,
)
from jd_agent.graphs.jd_extract.nodes.save_jd_sections.prompts import (
    build_system_prompt,
    build_user_message,
)
from jd_agent.graphs.jd_extract.state import JdExtractState
from jd_agent.integrations.supabase import jd_repository as jd_repo
from jd_agent.integrations.supabase.client import client_from_env
from jd_agent.integrations.supabase.prompt_config_repository import list_by_type


def save_jd_sections(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Structure ``jd_text`` into JD sections and persist them on ``jd_id``.

    Loads section definitions from ``agent_prompt_config``, runs the section
    parser agent, maps to Supabase sections jsonb, and upserts the row.
    """
    jd_text = str(state.get("jd_text") or "").strip()
    if not jd_text:
        raise ValueError("jd_text is required before save_jd_sections")

    client = client_from_env()
    config_rows = list_by_type(client, JD_SECTION_EXTRACTION)
    if not config_rows:
        raise ValueError(
            f"No agent_prompt_config rows for type={JD_SECTION_EXTRACTION!r}"
        )

    system_prompt = build_system_prompt(config_rows)
    user_message = build_user_message(jd_text, config_rows)

    parsed = invoke_section_parser(
        system_prompt=system_prompt,
        user_message=user_message,
        config=config,
    )

    sections = to_supabase_sections(parsed, state)
    jd = state.get("jd")
    jd_repo.upsert_sections(
        client,
        state["jd_id"],
        sections,
        title_name=(jd.title_name if jd is not None else None),
        company_name=(jd.company_name if jd is not None else None),
    )
    return {"jd_sections": parsed.model_dump(mode="json")}

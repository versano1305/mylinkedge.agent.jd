"""LangGraph nodes for the JD skills map-reduce subflow."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import Overwrite, Send
from mylinkedge_agent_tools.skill_matching import relevant_skills_from_text

from jd_agent.graphs.jd_extract.nodes.extract_jd_info.models import (
    SectionSkillResult,
    SectionSkillWorkerState,
    SectionWorkItem,
)
from jd_agent.graphs.jd_extract.nodes.extract_jd_info.prepare import (
    build_section_work_items,
)
from jd_agent.graphs.jd_extract.state import JdExtractState
from jd_agent.integrations.supabase import jd_repository as jd_repo
from jd_agent.integrations.supabase.client import client_from_env
from jd_agent.integrations.supabase.prompt_config_repository import (
    JD_SECTION_EXTRACTION,
    list_by_type,
)


def prepare_jd_info_sections(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Load enabled section configs and pair them with JD section content."""
    _ = config
    jd_id = str(state.get("jd_id") or "").strip()
    if not jd_id:
        raise ValueError("jd_id is required before prepare_jd_info_sections")

    client = client_from_env()
    sections = jd_repo.get_sections(client, jd_id)
    if not sections:
        raise ValueError(f"No sections saved for jd_id={jd_id}")

    config_rows = list_by_type(client, JD_SECTION_EXTRACTION)
    if not config_rows:
        raise ValueError(
            f"No agent_prompt_config rows for type={JD_SECTION_EXTRACTION!r}"
        )

    work_items = build_section_work_items(sections, config_rows)
    return {
        "section_tasks": [item.model_dump(mode="json") for item in work_items],
    }


def dispatch_section_skill_tasks(
    state: JdExtractState,
) -> list[Send] | str:
    """Fan out one map branch per section work item (or skip to save)."""
    tasks = state.get("section_tasks") or []
    if not tasks:
        return "save_jd_skills"

    sends: list[Send] = []
    for raw in tasks:
        item = (
            raw
            if isinstance(raw, SectionWorkItem)
            else SectionWorkItem.model_validate(raw)
        )
        sends.append(
            Send(
                "extract_section_skills",
                {
                    "section_task": item.model_dump(mode="json"),
                },
            )
        )
    return sends


def extract_section_skills(
    state: SectionSkillWorkerState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Match taxonomy skills for one JD section via ``relevant_skills_from_text``.

    Chunking / sentence splitting is handled inside the skill-matching tool.
    Keeps resolved skills only; unresolved drafts have ``is_existing=False``.
    Drops ``description`` so persisted skill payloads stay compact.
    Passes LangGraph ``config`` through so nested LLM/tool runs stay on the
    parent graph trace (LangSmith).
    """
    raw = state.get("section_task")
    if raw is None:
        raise ValueError("section_task is required for extract_section_skills")
    item = (
        raw if isinstance(raw, SectionWorkItem) else SectionWorkItem.model_validate(raw)
    )

    text = item.section_content.strip()
    skills: list[dict[str, Any]] = []
    if text:
        for skill in relevant_skills_from_text(text, config=config):
            payload = skill.model_dump(mode="json")
            if not payload.get("is_existing"):
                continue
            payload.pop("description", None)
            skills.append(payload)
    result = SectionSkillResult(section_key=item.section_key, skills=skills)
    return {"section_skill_results": [result.model_dump(mode="json")]}


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def initialize_missing_skill_fields(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Apply temporary P-1 fallback enrichment before persisting JD skills."""
    _ = config
    enriched_results: list[dict[str, Any]] = []
    for raw in state.get("section_skill_results") or []:
        result = (
            raw
            if isinstance(raw, SectionSkillResult)
            else SectionSkillResult.model_validate(raw)
        )
        skills: list[dict[str, Any]] = []
        for skill in result.skills:
            if not isinstance(skill, dict):
                continue
            payload = dict(skill)
            name = str(payload.get("name") or "").strip()
            if not name:
                continue
            if _is_missing(payload.get("surface_form")):
                payload["surface_form"] = name
            if _is_missing(payload.get("evidence_sentence")):
                payload["evidence_sentence"] = ""
            if _is_missing(payload.get("importance")):
                payload["importance"] = 1.0
            if "substitutable" not in payload or payload.get("substitutable") is None:
                payload["substitutable"] = False
            if "min_years" not in payload:
                payload["min_years"] = None
            skills.append(payload)
        enriched_results.append(
            SectionSkillResult(
                section_key=result.section_key,
                skills=skills,
            ).model_dump(mode="json")
        )
    return {"section_skill_results": Overwrite(enriched_results)}


def save_jd_skills(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Merge mapped section skills and persist them on ``job_description.skills``."""
    _ = config
    jd_id = str(state.get("jd_id") or "").strip()
    if not jd_id:
        raise ValueError("jd_id is required before save_jd_skills")

    combined: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in state.get("section_skill_results") or []:
        result = (
            raw
            if isinstance(raw, SectionSkillResult)
            else SectionSkillResult.model_validate(raw)
        )
        for skill in result.skills:
            if not isinstance(skill, dict):
                continue
            name = str(skill.get("name") or "").strip()
            if not name:
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            combined.append(dict(skill))

    client = client_from_env()
    jd_repo.upsert_skills(client, jd_id, skills=combined)

    # Skills live on the JD row; drop map-reduce intermediates from state.
    return {
        "section_tasks": [],
        "section_skill_results": Overwrite([]),
    }

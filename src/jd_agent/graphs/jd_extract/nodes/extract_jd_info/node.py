"""LangGraph nodes for the JD skills map-reduce subflow."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import Overwrite, Send
from mylinkedge_agent_tools.langgraph_streaming.annotations import emit_progress, thinking
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
from jd_agent.shared.jd_event_hub import publish_skill_linked_from_state

_REQUIRES_SKILL = "REQUIRES_SKILL"


@thinking("Preparing skill extraction sections…")
def prepare_jd_info_sections(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Load enabled section configs and pair them with JD section content."""
    _ = config
    jd_id = str(state.get("jd_id") or "").strip()
    if not jd_id:
        raise ValueError("jd_id is required before prepare_jd_info_sections")

    jd = state.get("jd")
    sections = jd.sections if jd is not None else {}
    if not sections:
        raise ValueError(f"No sections in state for jd_id={jd_id}")

    client = client_from_env()
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
    emit_progress("thinking", f"Extracting skills from section `{item.section_key}`…")

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


@thinking("Enriching extracted skills…")
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


def _requires_skill_links(
    jd_id: str,
    skills: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map persisted skill rows to ``JobDescription -[:REQUIRES_SKILL]-> Skill``."""
    links: list[dict[str, Any]] = []
    for skill in skills:
        skill_id = str(skill.get("id") or "").strip()
        if not skill_id:
            continue
        links.append(
            {
                "from_id": jd_id,
                "relationship": _REQUIRES_SKILL,
                "to_id": skill_id,
                "properties": {
                    key: value for key, value in skill.items() if key != "id"
                },
            }
        )
    return links


@thinking("Saving extracted skills…")
def save_jd_skills(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Merge mapped section skills and publish ``SKILL_LINKED``."""
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

    saved_skills = [
        jd_repo.JobDescriptionSkill.model_validate(skill) for skill in combined
    ]
    saved_payloads = [skill.model_dump(mode="json") for skill in saved_skills]
    publish_skill_linked_from_state(
        state,
        links=_requires_skill_links(jd_id, saved_payloads),
        context={"skills": saved_payloads},
        config=config,
    )

    updates: dict[str, Any] = {
        "section_tasks": [],
        "section_skill_results": Overwrite([]),
    }
    jd = state.get("jd")
    if jd is not None:
        updates["jd"] = jd.model_copy(update={"skills": saved_skills})
    return updates

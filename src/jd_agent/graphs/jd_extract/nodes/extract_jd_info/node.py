"""LangGraph nodes for the JD skills extraction subflow."""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.types import Overwrite
from mylinkedge_agent_tools.event_hub import (
    MAX_STATUS_BATCH,
    EventProcessingStatus,
    EventStatus,
    EventStatusClient,
    ExtractSkills,
    ExtractSkillsPayload,
    ExtractSkillsResult,
    GraphId,
    HubPublisher,
)
from mylinkedge_agent_tools.langgraph_streaming.annotations import emit_progress, thinking

from jd_agent.graphs.jd_extract.nodes.extract_jd_info.models import (
    SectionSkillExtractionRef,
    SectionSkillResult,
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
from jd_agent.shared.jd_event_hub import (
    _non_empty_str,
    _run_id_from_config,
    publish_skill_linked_from_state,
)

logger = logging.getLogger(__name__)
_REQUIRES_SKILL = "REQUIRES_SKILL"
_SKILL_EXTRACT_TIMEOUT_SECONDS = 300.0
_SKILL_EXTRACT_STATUS_HTTP_TIMEOUT_SECONDS = 30.0
_SKILL_EXTRACT_POLL_INTERVAL_SECONDS = 2.0


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


def route_section_skill_extraction(
    state: JdExtractState,
) -> Literal["extract_section_skills", "save_jd_skills"]:
    """Skip skill publish when there are no section tasks."""
    if state.get("section_tasks"):
        return "extract_section_skills"
    return "save_jd_skills"


@thinking("Publishing skill extractions…")
def extract_section_skills(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Publish one ``extract_skills`` event per section; results come from collect."""
    publisher = HubPublisher()
    jd_id = _non_empty_str(state.get("jd_id"))
    user_id = _non_empty_str(state.get("user_id"))
    run_id = _run_id_from_config(config)
    refs: list[dict[str, Any]] = []

    for raw in state.get("section_tasks") or []:
        item = (
            raw if isinstance(raw, SectionWorkItem) else SectionWorkItem.model_validate(raw)
        )
        text = item.section_content.strip()
        if not text:
            continue
        emit_progress("thinking", f"Extracting skills from section `{item.section_key}`…")

        context: dict[str, Any] = {"section_key": item.section_key}
        if jd_id:
            context["job_description_id"] = jd_id
        if run_id:
            context["run_id"] = run_id

        event = ExtractSkills(
            initiator=GraphId.JD_EXTRACT,
            user_id=user_id,
            payload=ExtractSkillsPayload(text=text, context=context),
        )
        publisher.publish(event)
        refs.append(
            SectionSkillExtractionRef(
                section_key=item.section_key,
                event_id=str(event.id),
            ).model_dump(mode="json")
        )

    return {"section_skill_extractions": Overwrite(refs)}


def _skills_from_extract_result(result: ExtractSkillsResult | None) -> list[dict[str, Any]]:
    """Keep hub-resolved skills from ``lookup_result.resolved`` only."""
    if result is None:
        return []
    skills: list[dict[str, Any]] = []
    for node in result.lookup_result.resolved:
        name = (node.name or "").strip()
        if not name:
            continue
        skill_id = (node.id or "").strip() or None
        surface = (
            (node.query.surface_form or node.query.name or name).strip() or name
        )
        evidence_sentence = (node.query.properties.get("evidence_sentence") or "").strip() or None
        aliases = node.query.properties.get("aliases") or []
        candidate_ids = node.query.properties.get("candidate_ids") or []
        skills.append(
            {
                "id": skill_id,
                "name": name,
                "surface_form": surface,
                "evidence_sentence": evidence_sentence,
                "candidate_ids": candidate_ids,
                "aliases": aliases,
            }
        )
    return skills


def summarize_event_status(status: EventStatus) -> str:
    """Summarize an event status for logging."""
    return f"event_id={status.event_id} status={status.status} error={status.error}"

def _poll_terminal_statuses(event_ids: list[str]) -> dict[str, EventStatus]:
    """Poll the hub with batched ``get_many`` until every event is terminal."""
    client = EventStatusClient(timeout=_SKILL_EXTRACT_STATUS_HTTP_TIMEOUT_SECONDS)
    deadline = time.monotonic() + _SKILL_EXTRACT_TIMEOUT_SECONDS
    terminal: dict[str, EventStatus] = {}
    while True:
        pending = [event_id for event_id in event_ids if event_id not in terminal]
        for start in range(0, len(pending), MAX_STATUS_BATCH):
            batch = client.get_many(pending[start : start + MAX_STATUS_BATCH])
            for status in batch.events:
                logger.debug("extract_skills status=%s", summarize_event_status(status))
                if status.is_terminal:
                    terminal[status.event_id] = status
        if len(terminal) == len(event_ids):
            return terminal
        if time.monotonic() >= deadline:
            waiting = [event_id for event_id in event_ids if event_id not in terminal]
            raise TimeoutError(
                f"extract_skills did not finish in time for events: {', '.join(waiting)}"
            )
        time.sleep(_SKILL_EXTRACT_POLL_INTERVAL_SECONDS)


@thinking("Collecting extracted skills…")
def collect_section_skill_results(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Wait for all published ``extract_skills`` events and map results per section."""
    _ = config
    refs = [
        SectionSkillExtractionRef.model_validate(raw)
        for raw in state.get("section_skill_extractions") or []
    ]
    statuses = _poll_terminal_statuses(list(dict.fromkeys(ref.event_id for ref in refs)))

    results: list[dict[str, Any]] = []
    for ref in refs:
        status = statuses[ref.event_id]
        if status.status != EventProcessingStatus.SUCCEEDED:
            detail = status.error.message if status.error else status.status
            raise RuntimeError(
                f"extract_skills {ref.event_id} for section {ref.section_key!r} failed: "
                f"{detail}"
            )
        skills = _skills_from_extract_result(status.result_as(ExtractSkillsResult))
        results.append(
            SectionSkillResult(section_key=ref.section_key, skills=skills).model_dump(
                mode="json"
            )
        )
    return {
        "section_skill_results": results,
        "section_skill_extractions": Overwrite([]),
    }


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

"""Publish JD-agent lifecycle events (event hub) from graph nodes."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.event_hub.contract import GraphId
from mylinkedge_agent_tools.event_hub.core.hub_publisher import HubPublisher
from mylinkedge_agent_tools.event_hub.expand import (
    SkillLinked,
    SkillLinkedLink,
    SkillLinkedPayload,
)
from mylinkedge_agent_tools.event_hub.lifecycle import (
    JdExtractionData,
    JdExtractionDataPayload,
    JdExtractionEnd,
    JdExtractionEndPayload,
    JdExtractionStart,
    JdExtractionStartPayload,
    JdGapAnalysisData,
    JdGapAnalysisDataPayload,
    JdGapAnalysisEnd,
    JdGapAnalysisEndPayload,
    JdGapAnalysisStart,
    JdGapAnalysisStartPayload,
    ResumeGenerateData,
    ResumeGenerateDataPayload,
    ResumeGenerateEnd,
    ResumeGenerateEndPayload,
    ResumeGenerateStart,
    ResumeGenerateStartPayload,
)
from mylinkedge_agent_tools.event_hub.lookup import (
    CompanyLookup,
    CompanyLookupPayload,
    UnresolvedNode,
)

from jd_agent.integrations.supabase.jd_repository import (
    JobDescription,
    JobDescriptionSkill,
)


def _lifecycle_publish_enabled() -> bool:
    return os.getenv("JD_LIFECYCLE_EVENTS_ENABLED", "1").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _non_empty_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _run_id_from_config(config: RunnableConfig | None) -> str | None:
    if not isinstance(config, dict):
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None
    return _non_empty_str(configurable.get("run_id")) or _non_empty_str(
        configurable.get("thread_id")
    )


def publish_jd_extraction_start(
    *,
    job_description_id: str,
    job_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    jd_id = job_description_id.strip()
    if not jd_id:
        return
    resolved_job_id = (job_id or jd_id).strip() or jd_id
    HubPublisher().publish(
        JdExtractionStart(
            initiator=GraphId.JD_EXTRACT,
            user_id=_non_empty_str(user_id),
            payload=JdExtractionStartPayload(
                job_id=resolved_job_id,
                job_description_id=jd_id,
                run_id=_non_empty_str(run_id),
            ),
        )
    )


def publish_jd_extraction_end(
    *,
    job_description_id: str,
    skills: list[dict[str, Any]] | None = None,
    sections: dict[str, Any] | None = None,
    job_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    jd_id = job_description_id.strip()
    if not jd_id:
        return
    resolved_job_id = (job_id or jd_id).strip() or jd_id
    HubPublisher().publish(
        JdExtractionEnd(
            initiator=GraphId.JD_EXTRACT,
            user_id=_non_empty_str(user_id),
            payload=JdExtractionEndPayload(
                job_id=resolved_job_id,
                job_description_id=jd_id,
                run_id=_non_empty_str(run_id),
                skills=list(skills or []),
                sections=dict(sections or {}),
            ),
        )
    )


def publish_jd_extraction_data(
    *,
    job_description_id: str,
    kind: str,
    data: Any,
    job_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    jd_id = job_description_id.strip()
    if not jd_id:
        return
    resolved_job_id = (job_id or jd_id).strip() or jd_id
    HubPublisher().publish(
        JdExtractionData(
            initiator=GraphId.JD_EXTRACT,
            user_id=_non_empty_str(user_id),
            payload=JdExtractionDataPayload(
                job_id=resolved_job_id,
                job_description_id=jd_id,
                run_id=_non_empty_str(run_id),
                kind=kind,
                data=data,
            ),
        )
    )


def publish_jd_gap_analysis_start(
    *,
    job_description_id: str,
    job_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    jd_id = job_description_id.strip()
    if not jd_id:
        return
    resolved_job_id = (job_id or jd_id).strip() or jd_id
    HubPublisher().publish(
        JdGapAnalysisStart(
            initiator=GraphId.GAP_COLLECT,
            user_id=_non_empty_str(user_id),
            payload=JdGapAnalysisStartPayload(
                job_id=resolved_job_id,
                job_description_id=jd_id,
                run_id=_non_empty_str(run_id),
            ),
        )
    )


def publish_jd_gap_analysis_data(
    *,
    job_description_id: str,
    kind: str,
    data: Any,
    job_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    jd_id = job_description_id.strip()
    if not jd_id:
        return
    resolved_job_id = (job_id or jd_id).strip() or jd_id
    HubPublisher().publish(
        JdGapAnalysisData(
            initiator=GraphId.GAP_COLLECT,
            user_id=_non_empty_str(user_id),
            payload=JdGapAnalysisDataPayload(
                job_id=resolved_job_id,
                job_description_id=jd_id,
                run_id=_non_empty_str(run_id),
                kind=kind,
                data=data,
            ),
        )
    )


def publish_jd_gap_analysis_end(
    *,
    job_description_id: str,
    job_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    jd_id = job_description_id.strip()
    if not jd_id:
        return
    resolved_job_id = (job_id or jd_id).strip() or jd_id
    HubPublisher().publish(
        JdGapAnalysisEnd(
            initiator=GraphId.GAP_COLLECT,
            user_id=_non_empty_str(user_id),
            payload=JdGapAnalysisEndPayload(
                job_id=resolved_job_id,
                job_description_id=jd_id,
                run_id=_non_empty_str(run_id),
            ),
        )
    )


def publish_resume_generate_start(
    *,
    job_id: str,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    resolved_job_id = job_id.strip()
    if not resolved_job_id:
        return
    HubPublisher().publish(
        ResumeGenerateStart(
            initiator=GraphId.RESUME_GENERATE,
            user_id=_non_empty_str(user_id),
            payload=ResumeGenerateStartPayload(
                job_id=resolved_job_id,
                run_id=_non_empty_str(run_id),
            ),
        )
    )


def publish_resume_generate_end(
    *,
    job_id: str,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    resolved_job_id = job_id.strip()
    if not resolved_job_id:
        return
    HubPublisher().publish(
        ResumeGenerateEnd(
            initiator=GraphId.RESUME_GENERATE,
            user_id=_non_empty_str(user_id),
            payload=ResumeGenerateEndPayload(
                job_id=resolved_job_id,
                run_id=_non_empty_str(run_id),
            ),
        )
    )


def publish_resume_generate_data(
    *,
    job_id: str,
    kind: str,
    data: Any,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    resolved_job_id = job_id.strip()
    if not resolved_job_id:
        return
    HubPublisher().publish(
        ResumeGenerateData(
            initiator=GraphId.RESUME_GENERATE,
            user_id=_non_empty_str(user_id),
            payload=ResumeGenerateDataPayload(
                job_id=resolved_job_id,
                run_id=_non_empty_str(run_id),
                kind=kind,
                data=data,
            ),
        )
    )


def publish_company_lookup(
    *,
    company_name: str,
    job_description_id: str | None = None,
    job_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    name = company_name.strip()
    if not name:
        return
    context: dict[str, Any] = {}
    jd_id = _non_empty_str(job_description_id)
    if jd_id:
        context["job_description_id"] = jd_id
        context["job_id"] = _non_empty_str(job_id) or jd_id
    resolved_run_id = _non_empty_str(run_id)
    if resolved_run_id:
        context["run_id"] = resolved_run_id
    HubPublisher().publish(
        CompanyLookup(
            initiator=GraphId.JD_EXTRACT,
            user_id=_non_empty_str(user_id),
            payload=CompanyLookupPayload(
                nodes=[UnresolvedNode(label="Company", name=name)],
                context=context,
            ),
        )
    )


def publish_company_lookup_from_state(
    state: dict[str, Any],
    *,
    company_name: str,
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``company_lookup`` from ``resolve_company``."""
    jd_id = _non_empty_str(state.get("jd_id"))
    publish_company_lookup(
        company_name=company_name,
        job_description_id=jd_id,
        job_id=_non_empty_str(state.get("job_id")) or jd_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_skill_linked(
    *,
    links: list[SkillLinkedLink] | list[dict[str, Any]],
    context: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    normalized = [
        link if isinstance(link, SkillLinkedLink) else SkillLinkedLink.model_validate(link)
        for link in links
    ]
    HubPublisher().publish(
        SkillLinked(
            initiator=GraphId.JD_EXTRACT,
            user_id=_non_empty_str(user_id),
            payload=SkillLinkedPayload(
                links=normalized,
                context=dict(context or {}),
            ),
        )
    )


def _is_skill_dict(item: dict[str, Any]) -> bool:
    if isinstance(item.get("name"), str):
        return True
    skill_id = item.get("id")
    return isinstance(skill_id, str) and bool(skill_id.strip())


def _saved_skill_payloads(skills: Any) -> list[dict[str, Any]]:
    """Dump skills in the shape previously persisted by ``upsert_skills``."""
    if not isinstance(skills, list):
        return []
    payloads: list[dict[str, Any]] = []
    for item in skills:
        if isinstance(item, JobDescriptionSkill):
            payloads.append(item.model_dump(mode="json"))
            continue
        if not isinstance(item, dict) or not _is_skill_dict(item):
            continue
        payload = dict(item)
        if not isinstance(payload.get("name"), str):
            payload["name"] = ""
        payloads.append(JobDescriptionSkill.model_validate(payload).model_dump(mode="json"))
    return payloads


def _skills_from_state(state: dict[str, Any]) -> list[Any]:
    jd = state.get("jd")
    if isinstance(jd, JobDescription):
        return list(jd.skills)
    if isinstance(jd, dict):
        skills = jd.get("skills")
        return list(skills) if isinstance(skills, list) else []
    return []


def _link_as_dict(link: SkillLinkedLink | dict[str, Any]) -> dict[str, Any]:
    if isinstance(link, SkillLinkedLink):
        return link.model_dump(mode="json")
    return dict(link)


def _enrich_links_with_saved_skills(
    links: list[SkillLinkedLink] | list[dict[str, Any]],
    skills: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {
        str(skill.get("id") or "").strip(): skill
        for skill in skills
        if str(skill.get("id") or "").strip()
    }
    enriched: list[dict[str, Any]] = []
    for link in links:
        raw = _link_as_dict(link)
        skill = by_id.get(str(raw.get("to_id") or "").strip())
        if skill:
            extra = {key: value for key, value in skill.items() if key != "id"}
            properties = dict(raw.get("properties") or {})
            raw["properties"] = {**extra, **properties}
        enriched.append(raw)
    return enriched


def publish_skill_linked_from_state(
    state: dict[str, Any],
    *,
    links: list[SkillLinkedLink] | list[dict[str, Any]],
    context: dict[str, Any] | None = None,
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``skill_linked`` from a ``jd_extract`` node.

    ``context.skills`` and each link's ``properties`` carry the full
    ``job_description.skills`` row shape (``requirement_level`` plus extractor
    extras such as ``aliases``, ``surface_form``, and ``evidence_sentence``).
    """
    jd_id = _non_empty_str(state.get("jd_id"))
    if not jd_id:
        return
    incoming = dict(context or {})
    if "skills" in incoming:
        saved_skills = _saved_skill_payloads(incoming.get("skills"))
    else:
        saved_skills = _saved_skill_payloads(_skills_from_state(state))
    merged_context = {
        "job_description_id": jd_id,
        "job_id": _non_empty_str(state.get("job_id")) or jd_id,
        "run_id": _run_id_from_config(config),
        **incoming,
        "skills": saved_skills,
    }
    publish_skill_linked(
        links=_enrich_links_with_saved_skills(links, saved_skills),
        context=merged_context,
        user_id=_non_empty_str(state.get("user_id")),
    )


def publish_jd_extraction_start_from_state(
    state: dict[str, Any],
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``jd_extraction_start`` from the first ``jd_extract`` node."""
    jd_id = _non_empty_str(state.get("jd_id"))
    if not jd_id:
        return
    publish_jd_extraction_start(
        job_description_id=jd_id,
        job_id=_non_empty_str(state.get("job_id")) or jd_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_jd_extraction_end_from_state(
    state: dict[str, Any],
    *,
    skills: list[dict[str, Any]] | None = None,
    sections: dict[str, Any] | None = None,
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``jd_extraction_end`` from ``mark_done``."""
    jd_id = _non_empty_str(state.get("jd_id"))
    if not jd_id:
        return
    publish_jd_extraction_end(
        job_description_id=jd_id,
        skills=skills,
        sections=sections,
        job_id=_non_empty_str(state.get("job_id")) or jd_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_jd_extraction_data_from_state(
    state: dict[str, Any],
    *,
    kind: str,
    data: Any,
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``jd_extraction_data`` from a ``jd_extract`` node."""
    jd_id = _non_empty_str(state.get("jd_id"))
    if not jd_id:
        return
    publish_jd_extraction_data(
        job_description_id=jd_id,
        kind=kind,
        data=data,
        job_id=_non_empty_str(state.get("job_id")) or jd_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_jd_gap_analysis_start_from_state(
    state: dict[str, Any],
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``jd_gap_analysis_start`` from the first ``gap_collect`` node."""
    jd_id = _non_empty_str(state.get("job_description_id"))
    session_id = _non_empty_str(state.get("session_id"))
    if not jd_id:
        return
    publish_jd_gap_analysis_start(
        job_description_id=jd_id,
        job_id=_non_empty_str(state.get("job_id")) or session_id or jd_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_jd_gap_analysis_data_from_state(
    state: dict[str, Any],
    *,
    kind: str,
    data: Any,
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``jd_gap_analysis_data`` from a ``gap_collect`` node."""
    jd_id = _non_empty_str(state.get("job_description_id"))
    session_id = _non_empty_str(state.get("session_id"))
    if not jd_id:
        return
    publish_jd_gap_analysis_data(
        job_description_id=jd_id,
        kind=kind,
        data=data,
        job_id=_non_empty_str(state.get("job_id")) or session_id or jd_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_jd_gap_analysis_end_from_state(
    state: dict[str, Any],
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``jd_gap_analysis_end`` from ``mark_done``."""
    jd_id = _non_empty_str(state.get("job_description_id"))
    session_id = _non_empty_str(state.get("session_id"))
    if not jd_id:
        return
    publish_jd_gap_analysis_end(
        job_description_id=jd_id,
        job_id=_non_empty_str(state.get("job_id")) or session_id or jd_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_resume_generate_start_from_state(
    state: dict[str, Any],
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``resume_generate_start`` from the first ``resume_generate`` node."""
    session_id = _non_empty_str(state.get("session_id"))
    job_id = _non_empty_str(state.get("job_id")) or session_id
    if not job_id:
        return
    publish_resume_generate_start(
        job_id=job_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_resume_generate_data_from_state(
    state: dict[str, Any],
    *,
    kind: str,
    data: Any,
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``resume_generate_data`` from ``assemble_and_save``."""
    session_id = _non_empty_str(state.get("session_id"))
    job_id = _non_empty_str(state.get("job_id")) or session_id
    if not job_id:
        return
    publish_resume_generate_data(
        job_id=job_id,
        kind=kind,
        data=data,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_resume_generate_end_from_state(
    state: dict[str, Any],
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``resume_generate_end`` from ``mark_done``."""
    session_id = _non_empty_str(state.get("session_id"))
    job_id = _non_empty_str(state.get("job_id")) or session_id
    if not job_id:
        return
    publish_resume_generate_end(
        job_id=job_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )

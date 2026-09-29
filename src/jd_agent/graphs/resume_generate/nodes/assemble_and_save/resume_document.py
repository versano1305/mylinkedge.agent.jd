"""Build the persistable JSON Resume document from graph state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from jd_agent.graphs.resume_generate.models import (
    Allocation,
    GeneratedInstance,
    InstanceBrief,
    SummaryResult,
)
from jd_agent.graphs.resume_generate.resume_schemas import (
    JSON_RESUME_SCHEMA_URL,
    JsonResumeAward,
    JsonResumeBasics,
    JsonResumeCertificate,
    JsonResumeEducation,
    JsonResumeLanguage,
    JsonResumeMeta,
    JsonResumePublication,
    JsonResumeSkill,
    JsonResumeVolunteer,
    JsonResumeWork,
    TailoredJsonResume,
)
from jd_agent.graphs.resume_generate.state import ResumeGenerateState


def _parse_models(
    static: dict[str, Any],
) -> tuple[
    JsonResumeBasics,
    list[JsonResumeEducation],
    list[JsonResumeCertificate],
    list[JsonResumeLanguage],
    list[JsonResumeAward],
    list[JsonResumePublication],
    list[JsonResumeVolunteer],
    list[JsonResumeSkill],
]:
    basics_raw = static.get("basics") if isinstance(static.get("basics"), dict) else {}
    basics = JsonResumeBasics.model_validate(basics_raw)

    def _list(key: str, model: type) -> list[Any]:
        raw = static.get(key)
        if not isinstance(raw, list):
            return []
        out: list[Any] = []
        for row in raw:
            if isinstance(row, dict):
                out.append(model.model_validate(row))
        return out

    return (
        basics,
        _list("education", JsonResumeEducation),
        _list("certificates", JsonResumeCertificate),
        _list("languages", JsonResumeLanguage),
        _list("awards", JsonResumeAward),
        _list("publications", JsonResumePublication),
        _list("volunteer", JsonResumeVolunteer),
        _list("skills", JsonResumeSkill),
    )


def build_work_entries(
    allocation: Allocation,
    instance_briefs: dict[str, Any],
    generated: dict[str, Any],
) -> list[JsonResumeWork]:
    """Merge brief headers with generated summaries and highlight strings."""

    work: list[JsonResumeWork] = []
    for instance_id in allocation.instance_order:
        raw_brief = instance_briefs.get(instance_id)
        if not isinstance(raw_brief, dict):
            continue
        brief = InstanceBrief.model_validate(raw_brief)
        payload_raw = generated.get(instance_id) or {}
        payload = GeneratedInstance.model_validate(payload_raw)

        end_date = brief.endDate
        work.append(
            JsonResumeWork(
                name=brief.company or None,
                position=brief.position or None,
                location=brief.location or None,
                startDate=brief.startDate,
                endDate=end_date,
                summary=payload.summary.strip() or None,
                highlights=[h.text for h in payload.highlights if h.text.strip()],
                instance_id=instance_id,
            )
        )
    return work


def _prune_empty_sections(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop empty list sections from the JSON Resume document."""

    pruned = dict(payload)
    for key in (
        "work",
        "volunteer",
        "education",
        "awards",
        "certificates",
        "publications",
        "skills",
        "languages",
        "interests",
        "references",
        "projects",
    ):
        if key in pruned and pruned[key] == []:
            del pruned[key]
    return pruned


def build_resume_document(state: ResumeGenerateState) -> dict[str, Any]:
    """Assemble and return a JSON Resume v1.0.0 dict (no pipeline-only fields)."""

    briefs = state.get("briefs") if isinstance(state.get("briefs"), dict) else {}
    static = briefs.get("static") if isinstance(briefs.get("static"), dict) else {}
    instances = briefs.get("instances") if isinstance(briefs.get("instances"), dict) else {}

    allocation_raw = state.get("allocation") if isinstance(state.get("allocation"), dict) else {}
    allocation = Allocation.model_validate(allocation_raw)

    generated = state.get("generated") if isinstance(state.get("generated"), dict) else {}

    summary_raw = state.get("summary") if isinstance(state.get("summary"), dict) else {}
    summary = SummaryResult.model_validate(summary_raw)

    jd = state.get("jd")
    session_id = str(state.get("session_id") or "")
    user_id = str(state.get("user_id") or "")
    jd_id = getattr(jd, "id", "") if jd is not None else ""

    (
        basics,
        education,
        certificates,
        languages,
        awards,
        publications,
        volunteer,
        skills,
    ) = _parse_models(static)

    if summary.text.strip():
        basics = basics.model_copy(update={"summary": summary.text.strip()})

    work = build_work_entries(allocation, instances, generated)
    last_modified = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    tailored = TailoredJsonResume(
        resume_id=session_id,
        user_id=user_id,
        jd_extraction_id=str(jd_id),
        schema_url=JSON_RESUME_SCHEMA_URL,
        basics=basics,
        work=work,
        education=education,
        certificates=certificates,
        languages=languages,
        awards=awards,
        publications=publications,
        volunteer=volunteer,
        skills=skills,
        meta=JsonResumeMeta(version="v1.0.0", lastModified=last_modified),
    )
    return _prune_empty_sections(tailored.to_json_resume())

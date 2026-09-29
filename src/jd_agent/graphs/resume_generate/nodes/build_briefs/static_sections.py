"""Deterministic JSON Resume sections (no LLM)."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.models import SkillRef
from jd_agent.graphs.resume_generate.nodes.allocate.work_instances import (
    experience_instances,
)
from jd_agent.graphs.resume_generate.resume_schemas import (
    JsonResumeAward,
    JsonResumeBasics,
    JsonResumeCertificate,
    JsonResumeEducation,
    JsonResumeLanguage,
    JsonResumeLocation,
    JsonResumeProfile,
    JsonResumePublication,
    JsonResumeVolunteer,
)
from jd_agent.shared.experience_intervals import parse_ym
from jd_agent.shared.text_similarity import best_label_match


def _edu_sort_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
    end = parse_ym(row.get("end") or row.get("endDate"))
    start = parse_ym(row.get("start") or row.get("startDate"))
    end_key = end or (0, 1)
    start_key = start or (0, 1)
    inst = str(row.get("institution_name") or row.get("node_id") or "")
    return (-end_key[0], -end_key[1], -start_key[0], inst)


def build_basics(
    dossier: dict[str, Any],
    jd_context: dict[str, Any],
) -> JsonResumeBasics:
    first = str(dossier.get("first_name") or dossier.get("firstName") or "")
    last = str(dossier.get("last_name") or dossier.get("lastName") or "")
    name = f"{first} {last}".strip()

    loc_raw = dossier.get("location") or {}
    location = None
    if isinstance(loc_raw, dict) and loc_raw:
        country = str(loc_raw.get("country") or "")
        location = JsonResumeLocation(
            city=str(loc_raw.get("city") or "") or None,
            region=str(loc_raw.get("state") or "") or None,
            countryCode=country[:2].upper() if len(country) >= 2 else None,
        )

    profiles: list[JsonResumeProfile] = []
    linkedin = str(dossier.get("linkedin") or "").strip()
    if linkedin:
        profiles.append(JsonResumeProfile(network="LinkedIn", url=linkedin))

    jd_title = str(jd_context.get("title") or "")
    label_candidates: list[str] = []
    tie_order: list[str] = []
    for exp in experience_instances(dossier):
        for candidate in [exp.position, *exp.position_aliases]:
            c = str(candidate or "").strip()
            if c and c not in label_candidates:
                label_candidates.append(c)
                tie_order.append(c)

    label = best_label_match(label_candidates, jd_title, tie_rank=tie_order)

    return JsonResumeBasics(
        name=name or None,
        label=label or None,
        email=str(dossier.get("email") or "") or None,
        phone=str(dossier.get("phone_number") or "") or None,
        location=location,
        profiles=profiles,
    )


def build_education(dossier: dict[str, Any]) -> list[JsonResumeEducation]:
    rows = [
        r
        for r in (dossier.get("raw_educations") or [])
        if isinstance(r, dict)
    ]
    rows.sort(key=_edu_sort_key)
    items: list[JsonResumeEducation] = []
    for row in rows:
        study = str(row.get("degree_level") or row.get("degree_name") or "").strip()
        area = str(row.get("specialization") or "").strip()
        courses_raw = row.get("courses") or []
        courses = [
            str(c.get("name") or c)
            for c in courses_raw
            if isinstance(c, dict) and c.get("name")
        ]
        items.append(
            JsonResumeEducation(
                institution=str(row.get("institution_name") or "") or None,
                studyType=study or None,
                area=area or None,
                startDate=row.get("start") or row.get("startDate"),
                endDate=row.get("end") or row.get("endDate"),
                score=str(row.get("gpa") or "") or None,
                courses=courses,
                instance_id=str(row.get("node_id") or "") or None,
            )
        )
    return items


def build_certificates(dossier: dict[str, Any]) -> list[JsonResumeCertificate]:
    items: list[JsonResumeCertificate] = []
    for cert in dossier.get("certificates") or []:
        if not isinstance(cert, dict):
            continue
        name = str(cert.get("name") or "").strip()
        if not name:
            continue
        items.append(
            JsonResumeCertificate(
                name=name,
                issuer=str(cert.get("issuer") or "") or None,
            )
        )
    return items


def build_languages(dossier: dict[str, Any]) -> list[JsonResumeLanguage]:
    items: list[JsonResumeLanguage] = []
    for row in dossier.get("languages") or []:
        if not isinstance(row, dict):
            continue
        lang = str(row.get("language") or "").strip()
        if not lang:
            continue
        items.append(
            JsonResumeLanguage(
                language=lang,
                fluency=str(row.get("level") or "") or None,
            )
        )
    return items


def build_awards(dossier: dict[str, Any]) -> list[JsonResumeAward]:
    items: list[JsonResumeAward] = []
    for row in dossier.get("awards") or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("name") or "").strip()
        if not title:
            continue
        items.append(
            JsonResumeAward(
                title=title,
                date=str(row.get("date") or "") or None,
                summary=str(row.get("description") or "") or None,
            )
        )
    return items


def build_publications(dossier: dict[str, Any]) -> list[JsonResumePublication]:
    items: list[JsonResumePublication] = []
    for row in dossier.get("publications") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        items.append(
            JsonResumePublication(
                name=name,
                releaseDate=str(row.get("publishedDate") or "") or None,
                summary=str(row.get("desc") or "") or None,
                url=str(row.get("url") or "") or None,
            )
        )
    return items


def build_volunteer(dossier: dict[str, Any]) -> list[JsonResumeVolunteer]:
    items: list[JsonResumeVolunteer] = []
    for row in dossier.get("volunteer") or []:
        if not isinstance(row, dict):
            continue
        org = str(row.get("company_name") or "").strip()
        vol_id = str(row.get("node_id") or "").strip()
        from jd_agent.integrations.skills_graph.candidate_dossier import _parse_date

        start = row.get("start") or _parse_date(row.get("startDate"))
        end = row.get("end") if row.get("end") is not None else _parse_date(row.get("endDate"))
        items.append(
            JsonResumeVolunteer(
                organization=org or None,
                position=str(row.get("organizationType") or "") or None,
                summary=str(row.get("summary") or "") or None,
                startDate=start,
                endDate=end,
                instance_id=vol_id or None,
            )
        )
    return items


def person_skill_refs(dossier: dict[str, Any]) -> list[SkillRef]:
    refs: list[SkillRef] = []
    for sk in dossier.get("skills") or []:
        if isinstance(sk, dict):
            refs.append(SkillRef.model_validate(sk))
    return refs

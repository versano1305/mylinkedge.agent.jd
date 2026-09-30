"""Candidate dossier reads from the Neo4j data database for resume generation.

All traversals are rooted at ``Person {ownerId: $user_id}`` — no
``Person.id`` is used or stored anywhere in this module.

Every Cypher node label and relationship type is resolved at **runtime** from
the taxonomy graph via :func:`jd_agent.graphs.resume_generate.taxonomy_types`,
so the query tracks taxonomy drift automatically. The built query string is
cached per process (the taxonomy is stable per deployment).
"""

from __future__ import annotations

import functools
import json
import re
from typing import Any

from mylinkedge_agent_tools.skills.settings import Neo4jSettings
from neo4j import Driver

from jd_agent.graphs.resume_generate.models import Dossier, Instance, SkillRef
from jd_agent.shared.evidence import parse_evidence
from jd_agent.graphs.resume_generate.taxonomy_types import edge_type, node_type
from jd_agent.integrations.skills_graph.user_skills import _get_driver


# ─── Date normalization ────────────────────────────────────────────────────────

_MONTH_ABBR: dict[str, str] = {
    "january": "01",   "february": "02", "march": "03",    "april": "04",
    "may":     "05",   "june":     "06", "july":  "07",    "august":    "08",
    "september": "09", "october":  "10", "november": "11", "december":  "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
}

_PRESENT_RE   = re.compile(r"^(present|current|now|ongoing)$", re.I)
_YYYY_MM_RE   = re.compile(r"^\d{4}-\d{2}$")
_YYYY_RE      = re.compile(r"^(\d{4})$")
_MON_YYYY_RE  = re.compile(r"^([A-Za-z]+)\s+(\d{4})$")
_MM_YYYY_RE   = re.compile(r"^(\d{1,2})/(\d{4})$")


def _parse_date(raw: str | None) -> str | None:
    """Normalize a free-text date to ``YYYY-MM``.

    Returns ``None`` for present/current/empty or unparseable input.
    Keeps the raw string separately (``raw_start`` / ``raw_end`` on Instance)
    so downstream units always have the original for display.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s or _PRESENT_RE.match(s):
        return None
    if _YYYY_MM_RE.match(s):
        return s
    m = _YYYY_RE.match(s)
    if m:
        return f"{m.group(1)}-01"
    m = _MON_YYYY_RE.match(s)
    if m:
        mon = _MONTH_ABBR.get(m.group(1).lower())
        if mon:
            return f"{m.group(2)}-{mon}"
    m = _MM_YYYY_RE.match(s)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    return None  # unparseable → treat as unknown / missing


# ─── SkillRef helpers ─────────────────────────────────────────────────────────

def _to_skill_ref(row: dict[str, Any]) -> SkillRef | None:
    skill_id = str(row.get("id") or "").strip()
    if not skill_id:
        return None
    return SkillRef(
        id=skill_id,
        name=str(row.get("name") or ""),
        skillType=str(row.get("skillType") or ""),
        evidence=parse_evidence(row.get("evidence")),
    )


def _skill_refs(rows: list[Any] | None) -> list[SkillRef]:
    """Convert a Cypher ``collect()`` result to a deduplicated SkillRef list."""
    seen: set[str] = set()
    result: list[SkillRef] = []
    for row in (rows or []):
        if not isinstance(row, dict):
            continue
        ref = _to_skill_ref(row)
        if ref and ref.id not in seen:
            seen.add(ref.id)
            result.append(ref)
    return result


# ─── Location helper ──────────────────────────────────────────────────────────

def _fmt_location(loc: dict[str, Any] | None) -> str:
    if not loc:
        return ""
    parts = [str(loc[k]) for k in ("city", "state", "country") if loc.get(k)]
    return ", ".join(parts)


# ─── Cypher query (built once per process from live taxonomy) ─────────────────

@functools.cache
def _dossier_query() -> str:
    """Return the Cypher dossier query with live taxonomy labels and rel-types.

    Calls :func:`~jd_agent.graphs.resume_generate.taxonomy_types.node_type`
    and :func:`~jd_agent.graphs.resume_generate.taxonomy_types.edge_type` at
    first call; the result is cached for the lifetime of the process.
    Tests patch ``taxonomy_types._taxonomy`` before the first call (see
    :class:`~jd_agent.graphs.resume_generate.taxonomy_types.MockTaxonomyTypes`).
    """
    # ── Node labels ───────────────────────────────────────────────────────────
    _Person               = node_type("Person")
    _ExperienceEvent      = node_type("ExperienceEvent")
    _Position             = node_type("Position")
    _Company              = node_type("Company")
    _Industry             = node_type("Industry")
    _Location             = node_type("Location")
    _Skill                = node_type("Skill")
    _Achievement          = node_type("Achievement")
    _Project              = node_type("Project")
    _Mentorship           = node_type("Mentorship")
    _EducationEvent       = node_type("EducationEvent")
    _EducationalInstitution = node_type("EducationalInstitution")
    _AcademicDegree       = node_type("AcademicDegree")
    _Specialization       = node_type("Specialization")
    _Course               = node_type("Course")
    _ProfessionalCertificate = node_type("ProfessionalCertificate")
    _LanguageProficiency  = node_type("LanguageProficiency")
    _SpokenLanguage       = node_type("SpokenLanguage")
    _Award                = node_type("Award")
    _Publication          = node_type("Publication")
    _VolunteerExperience  = node_type("VolunteerExperience")

    # ── Relationship types ────────────────────────────────────────────────────
    _LOCATED_IN_p        = edge_type("Person",              "Location")
    _HAD_EXPERIENCE      = edge_type("Person",              "ExperienceEvent")
    _HAS_POSITION        = edge_type("ExperienceEvent",     "Position")
    _AT_COMPANY          = edge_type("ExperienceEvent",     "Company")
    _IN_INDUSTRY         = edge_type("Company",             "Industry")
    _LOCATED_IN_exp      = edge_type("ExperienceEvent",     "Location")
    _USES_SKILL_exp      = edge_type("ExperienceEvent",     "Skill")
    _PRODUCED_exp        = edge_type("ExperienceEvent",     "Achievement")
    _VALIDATES_SKILL     = edge_type("Achievement",         "Skill")
    _WORKED_ON           = edge_type("ExperienceEvent",     "Project")
    _USES_SKILL_proj     = edge_type("Project",             "Skill")
    _PRODUCED_proj       = edge_type("Project",             "Achievement")
    _INCLUDED_MENTORSHIP = edge_type("ExperienceEvent",     "Mentorship")
    _TEACHES_SKILL       = edge_type("Mentorship",          "Skill")
    _HAD_EDUCATION       = edge_type("Person",              "EducationEvent")
    _FROM_INSTITUTION    = edge_type("EducationEvent",      "EducationalInstitution")
    _RESULTED_IN_DEGREE  = edge_type("EducationEvent",      "AcademicDegree")
    _HAS_SPECIALIZATION  = edge_type("AcademicDegree",      "Specialization")
    _LEARNED_SKILL       = edge_type("EducationEvent",      "Skill")
    _INCLUDES_COURSE     = edge_type("EducationEvent",      "Course")
    _RESULTED_IN_CERT    = edge_type("EducationEvent",      "ProfessionalCertificate")
    _CERTIFIES_SKILL     = edge_type("ProfessionalCertificate", "Skill")
    _HAS_SKILL           = edge_type("Person",              "Skill")
    _HAS_LANG_PROF       = edge_type("Person",              "LanguageProficiency")
    _IN_LANGUAGE         = edge_type("LanguageProficiency", "SpokenLanguage")
    _RECEIVED_AWARD      = edge_type("Person",              "Award")
    _AUTHORED            = edge_type("Person",              "Publication")
    _HAD_VOLUNTEER       = edge_type("Person",              "VolunteerExperience")
    _VOLUNTEERED_AT      = edge_type("VolunteerExperience", "Company")
    _USES_SKILL_vol      = edge_type("VolunteerExperience", "Skill")

    # Each branch is a separate CALL {} subquery to avoid Cartesian products.
    # Within multi-valued branches, collect() is called on each relationship
    # before the next OPTIONAL MATCH, maintaining one row per anchor node.
    # CASE WHEN … IS NOT NULL … END inside collect() drops null rows produced
    # by OPTIONAL MATCHes that find nothing.
    return f"""
MATCH (p:{_Person} {{ownerId: $user_id}})

// ── Person location ──────────────────────────────────────────────────────────
CALL {{
    WITH p
    OPTIONAL MATCH (p)-[:{_LOCATED_IN_p}]->(loc:{_Location})
    RETURN loc {{.city, .state, .country}} AS location
}}

// ── Experience branch ────────────────────────────────────────────────────────
CALL {{
    WITH p
    OPTIONAL MATCH (p)-[:{_HAD_EXPERIENCE}]->(exp:{_ExperienceEvent})
    // Collapse multi-valued header edges (position/company/industry/location)
    // before nested collects — otherwise cartesian rows duplicate each exp.
    OPTIONAL MATCH (exp)-[:{_HAS_POSITION}]->(pos:{_Position})
    WITH exp, head(collect(pos)) AS pos
    OPTIONAL MATCH (exp)-[:{_AT_COMPANY}]->(co:{_Company})
    WITH exp, pos, head(collect(co)) AS co
    OPTIONAL MATCH (co)-[:{_IN_INDUSTRY}]->(ind:{_Industry})
    WITH exp, pos, co, head(collect(ind)) AS ind
    OPTIONAL MATCH (exp)-[:{_LOCATED_IN_exp}]->(exploc:{_Location})
    WITH exp, pos, co, ind, head(collect(exploc)) AS exploc

    // Collect USES_SKILL edges before any multi-valued OPTIONAL MATCH
    OPTIONAL MATCH (exp)-[r_sk:{_USES_SKILL_exp}]->(sk:{_Skill})
    WITH exp, pos, co, ind, exploc,
         collect(CASE WHEN sk IS NOT NULL
                      THEN {{id: sk.id, name: sk.name, skillType: sk.skillType,
                             evidence: r_sk.evidence}}
                 END) AS exp_skills

    // Achievements — collect skills per achievement, then achievements per exp
    OPTIONAL MATCH (exp)-[:{_PRODUCED_exp}]->(ach:{_Achievement})
    WITH exp, pos, co, ind, exploc, exp_skills, ach
    OPTIONAL MATCH (ach)-[r_vsk:{_VALIDATES_SKILL}]->(vsk:{_Skill})
    WITH exp, pos, co, ind, exploc, exp_skills, ach,
         collect(CASE WHEN vsk IS NOT NULL
                      THEN {{id: vsk.id, name: vsk.name, skillType: vsk.skillType,
                             evidence: r_vsk.evidence}}
                 END) AS ach_skills
    WITH exp, pos, co, ind, exploc, exp_skills,
         collect(CASE WHEN ach IS NOT NULL
                      THEN {{node_id: elementId(ach), name: ach.name, desc: ach.desc,
                             impactValue: ach.impactValue, skills: ach_skills}}
                 END) AS achievements

    // Projects — collect proj skills, then proj achievements, then projects
    OPTIONAL MATCH (exp)-[:{_WORKED_ON}]->(proj:{_Project})
    WITH exp, pos, co, ind, exploc, exp_skills, achievements, proj
    OPTIONAL MATCH (proj)-[r_psk:{_USES_SKILL_proj}]->(psk:{_Skill})
    WITH exp, pos, co, ind, exploc, exp_skills, achievements, proj,
         collect(CASE WHEN psk IS NOT NULL
                      THEN {{id: psk.id, name: psk.name, skillType: psk.skillType,
                             evidence: r_psk.evidence}}
                 END) AS proj_skills
    OPTIONAL MATCH (proj)-[:{_PRODUCED_proj}]->(pach:{_Achievement})
    WITH exp, pos, co, ind, exploc, exp_skills, achievements, proj, proj_skills, pach
    OPTIONAL MATCH (pach)-[r_pvsk:{_VALIDATES_SKILL}]->(pvsk:{_Skill})
    WITH exp, pos, co, ind, exploc, exp_skills, achievements, proj, proj_skills, pach,
         collect(CASE WHEN pvsk IS NOT NULL
                      THEN {{id: pvsk.id, name: pvsk.name, skillType: pvsk.skillType,
                             evidence: r_pvsk.evidence}}
                 END) AS pach_skills
    WITH exp, pos, co, ind, exploc, exp_skills, achievements, proj, proj_skills,
         collect(CASE WHEN pach IS NOT NULL
                      THEN {{node_id: elementId(pach), name: pach.name, desc: pach.desc,
                             impactValue: pach.impactValue, skills: pach_skills}}
                 END) AS proj_achievements
    WITH exp, pos, co, ind, exploc, exp_skills, achievements,
         collect(CASE WHEN proj IS NOT NULL
                      THEN {{node_id: elementId(proj), name: proj.name,
                             summary: proj.summary, skills: proj_skills,
                             achievements: proj_achievements}}
                 END) AS projects

    // Mentorships — collect skills per mentorship, then mentorships per exp
    OPTIONAL MATCH (exp)-[:{_INCLUDED_MENTORSHIP}]->(ment:{_Mentorship})
    WITH exp, pos, co, ind, exploc, exp_skills, achievements, projects, ment
    OPTIONAL MATCH (ment)-[r_tsk:{_TEACHES_SKILL}]->(tsk:{_Skill})
    WITH exp, pos, co, ind, exploc, exp_skills, achievements, projects, ment,
         collect(CASE WHEN tsk IS NOT NULL
                      THEN {{id: tsk.id, name: tsk.name, skillType: tsk.skillType,
                             evidence: r_tsk.evidence}}
                 END) AS ment_skills
    WITH exp, pos, co, ind, exploc, exp_skills, achievements, projects,
         collect(CASE WHEN ment IS NOT NULL
                      THEN {{node_id: elementId(ment), summary: ment.summary,
                             count: ment.count, duration: ment.duration,
                             skills: ment_skills}}
                 END) AS mentorships

    RETURN collect(CASE WHEN exp IS NOT NULL THEN {{
        node_id:             elementId(exp),
        summary:             exp.summary,
        startDate:           exp.startDate,
        endDate:             exp.endDate,
        employmentType:      exp.employmentType,
        teamSize:            exp.teamSize,
        data_raw:            exp._data,
        position_name:       pos.name,
        position_alias:      pos._alias,
        company_name:        co.name,
        company_description: co.description,
        industry_name:       ind.name,
        location:            exploc {{.city, .state, .country}},
        skills:              exp_skills,
        achievements:        achievements,
        projects:            projects,
        mentorships:         mentorships
    }} END) AS experiences
}}

// ── Education branch ─────────────────────────────────────────────────────────
CALL {{
    WITH p
    OPTIONAL MATCH (p)-[:{_HAD_EDUCATION}]->(edu:{_EducationEvent})
    OPTIONAL MATCH (edu)-[:{_FROM_INSTITUTION}]->(inst:{_EducationalInstitution})
    OPTIONAL MATCH (edu)-[:{_RESULTED_IN_DEGREE}]->(deg:{_AcademicDegree})
    OPTIONAL MATCH (deg)-[:{_HAS_SPECIALIZATION}]->(spec:{_Specialization})
    WITH edu, inst, deg, spec

    OPTIONAL MATCH (edu)-[r_lsk:{_LEARNED_SKILL}]->(lsk:{_Skill})
    WITH edu, inst, deg, spec,
         collect(CASE WHEN lsk IS NOT NULL
                      THEN {{id: lsk.id, name: lsk.name, skillType: lsk.skillType,
                             evidence: r_lsk.evidence}}
                 END) AS learned_skills

    OPTIONAL MATCH (edu)-[:{_INCLUDES_COURSE}]->(course:{_Course})
    WITH edu, inst, deg, spec, learned_skills,
         collect(CASE WHEN course IS NOT NULL
                      THEN {{name: course.name, provider: course.provider}}
                 END) AS courses

    OPTIONAL MATCH (edu)-[:{_RESULTED_IN_CERT}]->(cert:{_ProfessionalCertificate})
    WITH edu, inst, deg, spec, learned_skills, courses, cert
    OPTIONAL MATCH (cert)-[:{_CERTIFIES_SKILL}]->(csk:{_Skill})
    WITH edu, inst, deg, spec, learned_skills, courses, cert,
         collect(CASE WHEN csk IS NOT NULL
                      THEN {{id: csk.id, name: csk.name, skillType: csk.skillType}}
                 END) AS cert_skills
    WITH edu, inst, deg, spec, learned_skills, courses,
         collect(CASE WHEN cert IS NOT NULL
                      THEN {{name: cert.name, issuer: cert.issuer, skills: cert_skills}}
                 END) AS certificates

    RETURN collect(CASE WHEN edu IS NOT NULL THEN {{
        node_id:          elementId(edu),
        summary:          edu.summary,
        startDate:        edu.startDate,
        endDate:          edu.endDate,
        gpa:              edu.gpa,
        institution_name: inst.name,
        degree_name:      deg.name,
        degree_level:     spec.level,
        specialization:   spec.name,
        learned_skills:   learned_skills,
        courses:          courses,
        certificates:     certificates
    }} END) AS educations
}}

// ── Person direct skills (HAS_SKILL — unverified profile claims) ─────────────
CALL {{
    WITH p
    OPTIONAL MATCH (p)-[r_hsk:{_HAS_SKILL}]->(hsk:{_Skill})
    RETURN collect(CASE WHEN hsk IS NOT NULL
                        THEN {{id: hsk.id, name: hsk.name, skillType: hsk.skillType,
                               evidence: r_hsk.evidence}}
                   END) AS has_skills
}}

// ── Languages ────────────────────────────────────────────────────────────────
CALL {{
    WITH p
    OPTIONAL MATCH (p)-[:{_HAS_LANG_PROF}]->(lp:{_LanguageProficiency})
        -[:{_IN_LANGUAGE}]->(lang:{_SpokenLanguage})
    RETURN collect(CASE WHEN lang IS NOT NULL
                        THEN {{language: lang.language, isoCode: lang.isoCode,
                               level: lp.level, notes: lp.notes}}
                   END) AS languages
}}

// ── Awards ───────────────────────────────────────────────────────────────────
CALL {{
    WITH p
    OPTIONAL MATCH (p)-[:{_RECEIVED_AWARD}]->(aw:{_Award})
    RETURN collect(CASE WHEN aw IS NOT NULL
                        THEN {{name: aw.name, date: aw.date,
                               description: aw.description}}
                   END) AS awards
}}

// ── Publications ─────────────────────────────────────────────────────────────
CALL {{
    WITH p
    OPTIONAL MATCH (p)-[:{_AUTHORED}]->(pub:{_Publication})
    RETURN collect(CASE WHEN pub IS NOT NULL
                        THEN {{name: pub.name, desc: pub.desc,
                               publishedDate: pub.publishedDate, url: pub.url}}
                   END) AS publications
}}

// ── Volunteer experience ─────────────────────────────────────────────────────
CALL {{
    WITH p
    OPTIONAL MATCH (p)-[:{_HAD_VOLUNTEER}]->(vol:{_VolunteerExperience})
    OPTIONAL MATCH (vol)-[:{_VOLUNTEERED_AT}]->(volco:{_Company})
    WITH vol, volco
    OPTIONAL MATCH (vol)-[r_vsk:{_USES_SKILL_vol}]->(vsk:{_Skill})
    WITH vol, volco,
         collect(CASE WHEN vsk IS NOT NULL
                      THEN {{id: vsk.id, name: vsk.name, skillType: vsk.skillType,
                             evidence: r_vsk.evidence}}
                 END) AS vol_skills
    RETURN collect(CASE WHEN vol IS NOT NULL THEN {{
        node_id:          elementId(vol),
        summary:          vol.summary,
        startDate:        vol.startDate,
        endDate:          vol.endDate,
        organizationType: vol.organizationType,
        company_name:     volco.name,
        skills:           vol_skills
    }} END) AS volunteer
}}

RETURN
    p.firstName    AS firstName,
    p.lastName     AS lastName,
    p.email        AS email,
    p.phone_number AS phone_number,
    p.linkedin     AS linkedin,
    p.address      AS address,
    location,
    experiences,
    educations,
    has_skills,
    languages,
    awards,
    publications,
    volunteer
"""


# ─── Row → Instance builders ──────────────────────────────────────────────────

def _position_aliases(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        return [text]
    return [str(raw).strip()]


def _exp_instances(exp_row: dict[str, Any]) -> list[Instance]:
    """Convert one experience Cypher row to a flat list of Instance objects.

    Returns the ExperienceEvent first, followed by its Achievement, Project
    (with nested project-level Achievements), and Mentorship sub-instances,
    each with ``parent_instance_id`` set to the owning node's element id.
    """
    exp_id = str(exp_row.get("node_id") or "")
    if not exp_id:
        return []

    # _data is often a JSON-string property with a 'heading' key used as a
    # display fallback when Position or Company are absent.
    heading = ""
    data_raw = exp_row.get("data_raw")
    if data_raw:
        try:
            dm = json.loads(data_raw) if isinstance(data_raw, str) else data_raw
            heading = str(dm.get("heading") or "") if isinstance(dm, dict) else ""
        except (json.JSONDecodeError, TypeError):
            pass

    raw_start = exp_row.get("startDate")
    raw_end = exp_row.get("endDate")

    instances: list[Instance] = [
        Instance(
            instance_id=exp_id,
            node_label=node_type("ExperienceEvent"),
            name=str(exp_row.get("position_name") or heading or ""),
            summary=str(exp_row.get("summary") or ""),
            start=_parse_date(raw_start),
            end=_parse_date(raw_end),
            raw_start=str(raw_start) if raw_start else None,
            raw_end=str(raw_end) if raw_end else None,
            company=str(exp_row.get("company_name") or ""),
            position=str(exp_row.get("position_name") or heading or ""),
            location=_fmt_location(exp_row.get("location")),
            employment_type=str(exp_row.get("employmentType") or ""),
            team_size=str(exp_row.get("teamSize") or ""),
            industry=str(exp_row.get("industry_name") or ""),
            company_description=str(exp_row.get("company_description") or ""),
            position_aliases=_position_aliases(exp_row.get("position_alias")),
            skills=_skill_refs(exp_row.get("skills")),
        )
    ]

    ach_label = node_type("Achievement")
    for ach in (exp_row.get("achievements") or []):
        if not isinstance(ach, dict):
            continue
        ach_id = str(ach.get("node_id") or "")
        if not ach_id:
            continue
        instances.append(Instance(
            instance_id=ach_id,
            node_label=ach_label,
            parent_instance_id=exp_id,
            name=str(ach.get("name") or ""),
            summary=str(ach.get("desc") or ach.get("name") or ""),
            impact_value=str(ach.get("impactValue") or "") or None,
            skills=_skill_refs(ach.get("skills")),
        ))

    proj_label = node_type("Project")
    for proj in (exp_row.get("projects") or []):
        if not isinstance(proj, dict):
            continue
        proj_id = str(proj.get("node_id") or "")
        if not proj_id:
            continue
        instances.append(Instance(
            instance_id=proj_id,
            node_label=proj_label,
            parent_instance_id=exp_id,
            name=str(proj.get("name") or ""),
            summary=str(proj.get("summary") or ""),
            skills=_skill_refs(proj.get("skills")),
        ))
        # Project-level achievements — parent is the project, not the exp
        for pach in (proj.get("achievements") or []):
            if not isinstance(pach, dict):
                continue
            pach_id = str(pach.get("node_id") or "")
            if not pach_id:
                continue
            instances.append(Instance(
                instance_id=pach_id,
                node_label=ach_label,
                parent_instance_id=proj_id,
                name=str(pach.get("name") or ""),
                summary=str(pach.get("desc") or pach.get("name") or ""),
                impact_value=str(pach.get("impactValue") or "") or None,
                skills=_skill_refs(pach.get("skills")),
            ))

    ment_label = node_type("Mentorship")
    for ment in (exp_row.get("mentorships") or []):
        if not isinstance(ment, dict):
            continue
        ment_id = str(ment.get("node_id") or "")
        if not ment_id:
            continue
        instances.append(Instance(
            instance_id=ment_id,
            node_label=ment_label,
            parent_instance_id=exp_id,
            summary=str(ment.get("summary") or ""),
            count=str(ment.get("count") or "") or None,
            duration=str(ment.get("duration") or "") or None,
            skills=_skill_refs(ment.get("skills")),
        ))

    return instances


def _edu_instance(edu_row: dict[str, Any]) -> Instance | None:
    """Convert one education Cypher row to an Instance (skills only; rich data
    goes into ``Dossier.raw_educations`` for WU-08).
    """
    edu_id = str(edu_row.get("node_id") or "")
    if not edu_id:
        return None
    raw_start = edu_row.get("startDate")
    raw_end = edu_row.get("endDate")
    degree = str(edu_row.get("degree_name") or "")
    level = str(edu_row.get("degree_level") or "")
    return Instance(
        instance_id=edu_id,
        node_label=node_type("EducationEvent"),
        name=str(edu_row.get("institution_name") or ""),
        summary=str(edu_row.get("summary") or ""),
        start=_parse_date(raw_start),
        end=_parse_date(raw_end),
        raw_start=str(raw_start) if raw_start else None,
        raw_end=str(raw_end) if raw_end else None,
        company=str(edu_row.get("institution_name") or ""),
        position=f"{level} {degree}".strip() if (level or degree) else "",
        skills=_skill_refs(edu_row.get("learned_skills")),
    )


def _vol_instance(vol_row: dict[str, Any]) -> Instance | None:
    """Convert one volunteer Cypher row to an Instance."""
    vol_id = str(vol_row.get("node_id") or "")
    if not vol_id:
        return None
    raw_start = vol_row.get("startDate")
    raw_end = vol_row.get("endDate")
    return Instance(
        instance_id=vol_id,
        node_label=node_type("VolunteerExperience"),
        summary=str(vol_row.get("summary") or ""),
        start=_parse_date(raw_start),
        end=_parse_date(raw_end),
        raw_start=str(raw_start) if raw_start else None,
        raw_end=str(raw_end) if raw_end else None,
        company=str(vol_row.get("company_name") or ""),
        employment_type=str(vol_row.get("organizationType") or ""),
        skills=_skill_refs(vol_row.get("skills")),
    )


def _normalize_edu_row(edu_row: dict[str, Any]) -> dict[str, Any]:
    """Return a date-normalized copy of a raw education row for raw_educations."""
    raw_start = edu_row.get("startDate")
    raw_end = edu_row.get("endDate")
    return {
        **edu_row,
        "start": _parse_date(raw_start),
        "end": _parse_date(raw_end),
        "raw_start": str(raw_start) if raw_start else None,
        "raw_end": str(raw_end) if raw_end else None,
    }


# ─── Public API ───────────────────────────────────────────────────────────────

def fetch_candidate_dossier(
    user_id: str,
    *,
    driver: Driver | None = None,
) -> Dossier:
    """Load all resume-relevant data for ``ownerId = user_id`` in one round-trip.

    Returns an empty :class:`~jd_agent.graphs.resume_generate.models.Dossier`
    when no ``Person`` node exists for the owner (defensive fallback; WU-01
    already guarantees at most one Person per owner before this is called).

    A ``driver`` may be injected for tests; production uses the cached driver
    from :func:`~jd_agent.integrations.skills_graph.user_skills._get_driver`.
    """
    uid = (user_id or "").strip()
    if not uid:
        return Dossier(user_id=user_id)

    active_driver = driver or _get_driver()
    database = Neo4jSettings.from_env().resolved_data_database

    with active_driver.session(database=database) as session:
        record = session.run(_dossier_query(), user_id=uid).single()

    if record is None:
        return Dossier(user_id=user_id)

    row = dict(record)

    # ── Person basics ─────────────────────────────────────────────────────────
    loc = row.get("location") or {}

    # ── Instances (experiences + sub-nodes + education + volunteer) ───────────
    instances: list[Instance] = []
    seen_experience_ids: set[str] = set()

    for exp_row in (row.get("experiences") or []):
        if not isinstance(exp_row, dict):
            continue
        exp_id = str(exp_row.get("node_id") or "")
        if exp_id and exp_id in seen_experience_ids:
            continue
        if exp_id:
            seen_experience_ids.add(exp_id)
        instances.extend(_exp_instances(exp_row))

    raw_educations: list[dict[str, Any]] = []
    for edu_row in (row.get("educations") or []):
        if not isinstance(edu_row, dict):
            continue
        inst = _edu_instance(edu_row)
        if inst:
            instances.append(inst)
        raw_educations.append(_normalize_edu_row(edu_row))

    for vol_row in (row.get("volunteer") or []):
        if isinstance(vol_row, dict):
            inst = _vol_instance(vol_row)
            if inst:
                instances.append(inst)

    # ── Person direct skills (HAS_SKILL — profile / skills section) ───────────
    person_skills = _skill_refs(row.get("has_skills"))

    # ── Certificates (from education branch, RESULTED_IN_PROFESSIONAL_CERTIFICATE)
    certificates: list[dict[str, Any]] = []
    for edu_row in (row.get("educations") or []):
        if isinstance(edu_row, dict):
            for cert in (edu_row.get("certificates") or []):
                if isinstance(cert, dict) and cert.get("name"):
                    certificates.append(cert)

    return Dossier(
        user_id=user_id,
        first_name=str(row.get("firstName") or ""),
        last_name=str(row.get("lastName") or ""),
        email=str(row.get("email") or ""),
        phone_number=str(row.get("phone_number") or ""),
        linkedin=str(row.get("linkedin") or ""),
        address=str(row.get("address") or ""),
        location=dict(loc) if loc else {},
        instances=instances,
        raw_educations=raw_educations,
        certificates=certificates,
        languages=[
            d for d in (row.get("languages") or []) if isinstance(d, dict)
        ],
        awards=[
            d for d in (row.get("awards") or []) if isinstance(d, dict)
        ],
        publications=[
            d for d in (row.get("publications") or []) if isinstance(d, dict)
        ],
        volunteer=[
            d for d in (row.get("volunteer") or []) if isinstance(d, dict)
        ],
        skills=person_skills,
    )

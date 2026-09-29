"""Orchestration for WU-08 generation briefs and static resume sections."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.models import Allocation
from jd_agent.graphs.resume_generate.nodes.build_briefs.instance_briefs import (
    build_instance_briefs,
    generatable_instance_ids,
)
from jd_agent.graphs.resume_generate.nodes.build_briefs.skills_section import (
    build_skills_section,
)
from jd_agent.graphs.resume_generate.nodes.build_briefs.static_sections import (
    build_awards,
    build_basics,
    build_certificates,
    build_education,
    build_languages,
    build_publications,
    build_volunteer,
)
from jd_agent.graphs.resume_generate.nodes.build_briefs.years_facts import (
    build_years_facts,
)
from jd_agent.shared.skill_closures import Edge


def run_build_briefs(
    dossier: dict[str, Any],
    allocation: Allocation,
    atoms: list[dict[str, Any]],
    demand: dict[str, Any],
    jd_targets: list[dict[str, Any]],
    jd_context: dict[str, Any],
    edges: list[Edge],
    skill_meta: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Build instance briefs, static JSON Resume sections, and years facts."""

    instance_briefs = build_instance_briefs(dossier, allocation, atoms)
    generatable_ids = generatable_instance_ids(instance_briefs, allocation)
    skills, skills_sources, skill_group_labels = build_skills_section(
        dossier, atoms, demand, jd_targets, edges, skill_meta
    )
    years_facts = build_years_facts(dossier, atoms, jd_targets)

    static = {
        "basics": build_basics(dossier, jd_context).model_dump(exclude_none=True),
        "education": [
            e.model_dump(exclude_none=True) for e in build_education(dossier)
        ],
        "certificates": [
            c.model_dump(exclude_none=True) for c in build_certificates(dossier)
        ],
        "languages": [
            lang.model_dump(exclude_none=True) for lang in build_languages(dossier)
        ],
        "awards": [a.model_dump(exclude_none=True) for a in build_awards(dossier)],
        "publications": [
            p.model_dump(exclude_none=True) for p in build_publications(dossier)
        ],
        "volunteer": [
            v.model_dump(exclude_none=True) for v in build_volunteer(dossier)
        ],
        "skills": [s.model_dump(exclude_none=True) for s in skills],
    }

    return {
        "instances": {
            iid: brief.model_dump() for iid, brief in instance_briefs.items()
        },
        "generatable_instance_ids": generatable_ids,
        "static": static,
        "years_facts": years_facts,
        "skills_sources": skills_sources,
        "skill_group_labels": skill_group_labels,
    }

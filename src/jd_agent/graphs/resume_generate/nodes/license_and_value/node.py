"""WU-06 — Per-atom JD licensing and standalone value."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.models import Atom
from jd_agent.graphs.resume_generate.nodes.license_and_value.enrich import enrich_atoms
from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.integrations.skills_graph import get_skills_graph
from jd_agent.shared.skill_closures import Edge, make_is_domain


def license_and_value(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Attach ``licensed`` / ``adjacent`` terms and ``standalone_value`` to atoms."""

    _ = config
    raw_atoms = state.get("atoms")
    if raw_atoms is None:
        raise ValueError("atoms is required before license_and_value")

    demand = state.get("demand")
    if not isinstance(demand, dict) or not demand.get("d_star"):
        raise ValueError("demand with d_star is required before license_and_value")

    dossier = state.get("dossier")
    if not isinstance(dossier, dict):
        raise ValueError("dossier is required before license_and_value")

    jd_targets = list(state.get("jd_targets") or [])
    jd_domains = list(state.get("jd_domains") or [])

    skills_graph = get_skills_graph()
    skill_meta: dict[str, dict[str, str]] = {
        nid: {"name": node.name, "skillType": node.skill_type}
        for nid, node in skills_graph.nodes.items()
    }
    is_domain = make_is_domain(skill_meta)

    edges_subset: list[Edge] = list(demand.get("edges_subset") or [])
    if not edges_subset:
        edges_subset = [
            (e.source, e.target, e.type) for e in skills_graph.edges
        ]

    enriched = enrich_atoms(
        list(raw_atoms),
        dossier=dossier,
        demand=demand,
        jd_targets=jd_targets,
        jd_domains=jd_domains,
        edges_subset=edges_subset,
        is_domain=is_domain,
    )

    return {
        "atoms": [
            Atom.model_validate(a).model_dump(mode="json") for a in enriched
        ]
    }

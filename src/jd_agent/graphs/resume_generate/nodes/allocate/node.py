"""WU-07 — Select resume lines under template budget."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.constants import DEFAULT_TEMPLATE
from jd_agent.graphs.resume_generate.nodes.allocate.pipeline import run_allocation
from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.integrations.skills_graph import get_skills_graph
from jd_agent.shared.skill_closures import make_is_domain


def allocate(state: ResumeGenerateState, config: RunnableConfig) -> dict[str, Any]:
    """Choose atoms and per-role line budgets maximizing resume JD fit."""

    _ = config
    demand = state.get("demand")
    if not isinstance(demand, dict) or not demand.get("d_star"):
        raise ValueError("demand with d_star is required before allocate")

    dossier = state.get("dossier")
    if not isinstance(dossier, dict):
        raise ValueError("dossier is required before allocate")

    atoms = list(state.get("atoms") or [])
    template = state.get("template") or DEFAULT_TEMPLATE
    jd_context = state.get("jd_context") if isinstance(state.get("jd_context"), dict) else {}

    skills_graph = get_skills_graph()
    skill_meta: dict[str, dict[str, str]] = {
        nid: {"name": node.name, "skillType": node.skill_type}
        for nid, node in skills_graph.nodes.items()
    }
    edges = [(e.source, e.target, e.type) for e in skills_graph.edges]
    is_domain = make_is_domain(skill_meta)

    allocation = run_allocation(
        dossier,
        atoms,
        demand,
        template,
        jd_context,
        edges,
        is_domain,
    )
    return {"allocation": allocation.model_dump()}

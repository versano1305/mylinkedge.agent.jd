"""WU-08 — Generation briefs and deterministic resume sections."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.models import Allocation
from jd_agent.graphs.resume_generate.nodes.build_briefs.pipeline import (
    run_build_briefs,
)
from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.integrations.skills_graph import get_skills_graph


def build_briefs(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Produce per-instance briefs and static JSON Resume sections."""

    _ = config
    dossier = state.get("dossier")
    if not isinstance(dossier, dict):
        raise ValueError("dossier is required before build_briefs")

    allocation_raw = state.get("allocation")
    if not isinstance(allocation_raw, dict) or "instance_order" not in allocation_raw:
        raise ValueError("allocation with instance_order is required before build_briefs")

    demand = state.get("demand")
    if not isinstance(demand, dict) or not demand.get("d_star"):
        raise ValueError("demand with d_star is required before build_briefs")

    allocation = Allocation.model_validate(allocation_raw)
    atoms = list(state.get("atoms") or [])
    jd_targets = list(state.get("jd_targets") or [])
    jd_context = state.get("jd_context") if isinstance(state.get("jd_context"), dict) else {}

    skills_graph = get_skills_graph()
    skill_meta: dict[str, dict[str, str]] = {
        nid: {"name": node.name, "skillType": node.skill_type}
        for nid, node in skills_graph.nodes.items()
    }
    edges = [(e.source, e.target, e.type) for e in skills_graph.edges]

    briefs = run_build_briefs(
        dossier,
        allocation,
        atoms,
        demand,
        jd_targets,
        jd_context,
        edges,
        skill_meta,
    )
    return {"briefs": briefs}

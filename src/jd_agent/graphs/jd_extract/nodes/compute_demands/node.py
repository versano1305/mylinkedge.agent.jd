"""LangGraph node: demand closure over extracted JD skills."""

from __future__ import annotations

import math
from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.langgraph_streaming.annotations import thinking

from jd_agent.graphs.jd_extract.state import JdExtractState
from jd_agent.integrations.skills_graph._bootstrap import ensure_shared_on_path
from jd_agent.integrations.supabase.jd_repository import JobDescription, JobDescriptionSkill
from jd_agent.shared.jd_event_hub import publish_jd_extraction_data_from_state

ensure_shared_on_path()

from mylinkedge_agent_tools.graph_algorithms import (  # noqa: E402
    DemandPropagationRequest,
    DemandPropagationResult,
    GraphAlgorithmsClient,
)


def _demand_weight(skill: JobDescriptionSkill) -> float:
    """Read a positive seed weight. ``importance`` wins; else ``requirement_level``."""

    raw = skill.model_dump()
    value = raw.get("importance")
    if value is None:
        value = raw.get("requirement_level", 1.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1.0
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        return 0.0
    return min(1.0, number)


def demand_seeds(skills: list[JobDescriptionSkill]) -> dict[str, float]:
    """Map resolved skill ids to demand weights. Unresolved skills are omitted."""

    seeds: dict[str, float] = {}
    for skill in skills:
        skill_id = str(skill.id or "").strip()
        if not skill_id:
            continue
        weight = _demand_weight(skill)
        if weight <= 0:
            continue
        current = seeds.get(skill_id)
        if current is None or weight > current:
            seeds[skill_id] = weight
    return seeds


def _demands_payload(
    seeds: dict[str, float],
    result: DemandPropagationResult,
) -> dict[str, Any]:
    return {
        "d_star": {sid: round(result.d_star[sid], 4) for sid in sorted(result.d_star)},
        "seeds": {sid: round(seeds[sid], 4) for sid in sorted(seeds)},
        "meta": result.meta,
    }


@thinking("Computing skill demands…")
def compute_demands(
    state: JdExtractState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Run demand closure on saved JD skills and publish ``JD_EXTRACTION_DATA``.

    Seeds are the skill ids written by ``save_jd_skills``. ``compute_demand``
    walks ``REQUIRES`` / ``USES`` and the payload is published for an
    event-hub consumer, the same way sections are.
    """
    raw_jd = state.get("jd")
    if raw_jd is None:
        raise ValueError("jd is required before compute_demands")
    jd = raw_jd if isinstance(raw_jd, JobDescription) else JobDescription.model_validate(raw_jd)

    seeds = demand_seeds(list(jd.skills))
    result = GraphAlgorithmsClient().compute_demand(DemandPropagationRequest(seeds=seeds))
    demands = _demands_payload(seeds, result)
    publish_jd_extraction_data_from_state(
        state,
        kind="demands",
        data={
            "demands": demands,
            "title_name": jd.title_name,
            "company_name": jd.company_name,
        },
        config=config,
    )
    return {"jd_demands": demands}

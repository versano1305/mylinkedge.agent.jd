"""Rank interview candidates by expected yield and finalize the gaps payload."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.gap_collect.nodes.rank_queue.ranking import rank_candidates
from jd_agent.graphs.gap_collect.state import GapCollectState


def rank_queue_node(
    state: GapCollectState, config: RunnableConfig
) -> dict[str, Any]:
    """Attach the expected-yield-ordered ``interview`` block to ``gaps``."""
    _ = config
    gaps = dict(state.get("gaps") or {})
    if not gaps:
        raise ValueError("gaps must be computed before rank_queue")

    candidates = list(state.get("interview_candidates") or [])
    gaps["interview"] = rank_candidates(candidates)
    return {"gaps": gaps}

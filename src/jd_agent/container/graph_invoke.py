"""Invoke a compiled graph from a container host."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mylinkedge_agent_tools.event_hub import HandlerPermanentError


def default_graphs() -> dict[str, Any]:
    """Compiled graphs hosted by this service."""

    from jd_agent.graphs.gap_collect.gap_collect_graph import graph as gap_collect
    from jd_agent.graphs.jd_extract.jd_extract_graph import graph as jd_extract
    from jd_agent.graphs.resume_generate.resume_generate_graph import (
        graph as resume_generate,
    )

    return {
        "jd_extract": jd_extract,
        "gap_collect": gap_collect,
        "resume_generate": resume_generate,
    }


class GraphInvoker:
    """Run one named graph and return its final state."""

    def __init__(self, graphs: Mapping[str, Any] | None = None) -> None:
        self._graphs = dict(default_graphs() if graphs is None else graphs)

    async def invoke(
        self,
        graph_id: str,
        graph_input: dict[str, Any],
        *,
        thread_id: str | None,
    ) -> dict[str, Any]:
        graph = self._graphs.get(graph_id)
        if graph is None:
            raise HandlerPermanentError(f"unknown graph {graph_id}")
        config = _run_config(thread_id)
        if config is None:
            result = await graph.ainvoke(graph_input)
        else:
            result = await graph.ainvoke(graph_input, config)
        if isinstance(result, dict):
            return result
        return {}


def _run_config(thread_id: str | None) -> dict[str, Any] | None:
    if not thread_id:
        return None
    return {"configurable": {"thread_id": thread_id, "run_id": thread_id}}

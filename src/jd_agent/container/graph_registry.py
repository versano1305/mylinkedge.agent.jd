"""Register JD agent LangGraphs with ``GraphTurnService``."""

from __future__ import annotations

from typing import Any

from mylinkedge_agent_tools.langgraph_streaming.config import TurnCompletionConfig
from mylinkedge_agent_tools.langgraph_streaming.grpc.registry import (
    GraphRegistry,
    GraphSpec,
)

from jd_agent.container.queued_inputs import (
    GAP_COLLECT_GRAPH,
    JD_EXTRACT_GRAPH,
    RESUME_GENERATE_GRAPH,
)
from jd_agent.graphs.gap_collect.gap_collect_graph import builder as gap_collect_builder
from jd_agent.graphs.jd_extract.jd_extract_graph import builder as jd_extract_builder
from jd_agent.graphs.resume_generate.resume_generate_graph import (
    builder as resume_generate_builder,
)
from jd_agent.shared.mongo import get_mongo_checkpointer


def _jd_extract_bootstrap(body: dict[str, Any]) -> dict[str, Any]:
    jd_id = str(body.get("jd_id") or "").strip()
    if not jd_id:
        raise ValueError("jd_id is required")
    return {"jd_id": jd_id}


def _gap_collect_bootstrap(body: dict[str, Any]) -> dict[str, Any]:
    session_id = str(body.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required")
    return {"session_id": session_id}


def _resume_generate_bootstrap(body: dict[str, Any]) -> dict[str, Any]:
    session_id = str(body.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required")
    return {"session_id": session_id}


def build_graph_registry() -> GraphRegistry:
    """Build a registry for gRPC/HTTP turn APIs (all hosted graphs).

    Graphs are recompiled with a MongoDB checkpointer so ``get_state`` /
    thread continuity work in ``GraphTurnServicer`` (module-level graphs used
    by SQS remain checkpointer-free).
    """
    checkpointer = get_mongo_checkpointer()
    graphs = {
        JD_EXTRACT_GRAPH: jd_extract_builder.compile(
            checkpointer=checkpointer,
            name="jd-extract",
        ),
        GAP_COLLECT_GRAPH: gap_collect_builder.compile(
            checkpointer=checkpointer,
            name="gap-collect",
        ),
        RESUME_GENERATE_GRAPH: resume_generate_builder.compile(
            checkpointer=checkpointer,
            name="resume-generate",
        ),
    }
    registry = GraphRegistry()

    registry.register(
        JD_EXTRACT_GRAPH,
        GraphSpec(
            graph=graphs[JD_EXTRACT_GRAPH],
            bootstrap_input=_jd_extract_bootstrap,
            completion=TurnCompletionConfig(
                phase_state_key="extraction_status",
                complete_when=lambda phase: phase == "done",
            ),
            state_keys=("extraction_status", "jd_id", "company_id"),
        ),
    )
    registry.register(
        GAP_COLLECT_GRAPH,
        GraphSpec(
            graph=graphs[GAP_COLLECT_GRAPH],
            bootstrap_input=_gap_collect_bootstrap,
            completion=TurnCompletionConfig(
                phase_state_key="gap_status",
                complete_when=lambda phase: phase == "done",
            ),
            state_keys=("gap_status", "session_id", "job_description_id"),
        ),
    )
    registry.register(
        RESUME_GENERATE_GRAPH,
        GraphSpec(
            graph=graphs[RESUME_GENERATE_GRAPH],
            bootstrap_input=_resume_generate_bootstrap,
            completion=TurnCompletionConfig(
                phase_state_key="generate_status",
                complete_when=lambda phase: phase == "done",
            ),
            state_keys=("generate_status", "session_id"),
        ),
    )
    return registry

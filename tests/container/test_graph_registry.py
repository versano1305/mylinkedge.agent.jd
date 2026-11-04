"""gRPC graph registry."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from jd_agent.container.graph_registry import build_graph_registry
from jd_agent.container.queued_inputs import (
    GAP_COLLECT_GRAPH,
    JD_EXTRACT_GRAPH,
    RESUME_GENERATE_GRAPH,
)


@pytest.fixture
def registry():
    with patch(
        "jd_agent.container.graph_registry.get_mongo_checkpointer",
        return_value=MemorySaver(),
    ):
        yield build_graph_registry()


def test_registry_includes_all_hosted_graphs(registry) -> None:
    assert registry.graph_ids() == [
        GAP_COLLECT_GRAPH,
        JD_EXTRACT_GRAPH,
        RESUME_GENERATE_GRAPH,
    ]


def test_registry_graphs_have_checkpointer(registry) -> None:
    for graph_id in (JD_EXTRACT_GRAPH, GAP_COLLECT_GRAPH, RESUME_GENERATE_GRAPH):
        graph = registry.get(graph_id).resolve_graph()
        assert getattr(graph, "checkpointer", None) is not None


def test_jd_extract_bootstrap_requires_jd_id(registry) -> None:
    spec = registry.get(JD_EXTRACT_GRAPH)
    assert spec.bootstrap_input is not None
    with pytest.raises(ValueError, match="jd_id"):
        spec.bootstrap_input({})
    assert spec.bootstrap_input({"jd_id": " jd-1 "}) == {"jd_id": "jd-1"}


def test_gap_collect_bootstrap_requires_session_id(registry) -> None:
    spec = registry.get(GAP_COLLECT_GRAPH)
    assert spec.bootstrap_input is not None
    with pytest.raises(ValueError, match="session_id"):
        spec.bootstrap_input({})
    assert spec.bootstrap_input({"session_id": " sess-9 "}) == {"session_id": "sess-9"}


def test_resume_generate_bootstrap_requires_session_id(registry) -> None:
    spec = registry.get(RESUME_GENERATE_GRAPH)
    assert spec.bootstrap_input is not None
    with pytest.raises(ValueError, match="session_id"):
        spec.bootstrap_input({})
    assert spec.bootstrap_input({"session_id": " sess-2 "}) == {"session_id": "sess-2"}

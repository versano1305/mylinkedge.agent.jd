"""Tests that the gap collection graph compiles with the expected shape."""

from jd_agent.graphs.gap_collect.gap_collect_graph import graph


def test_gap_collect_graph_compiles() -> None:
    assert graph is not None
    assert graph.name == "gap-collect"


def test_gap_collect_graph_has_expected_nodes() -> None:
    node_names = set(graph.get_graph().nodes)
    for name in (
        "load_session",
        "mark_analyzing",
        "load_jd_targets",
        "load_user_skills",
        "compute_gaps",
        "rank_queue",
        "save_gaps",
        "mark_done",
    ):
        assert name in node_names

"""WU-12 mark_done node."""

from __future__ import annotations

from jd_agent.graphs.resume_generate.nodes.mark_done.node import mark_done


def test_mark_done_is_no_op() -> None:
    result = mark_done({"session_id": "sess-1"}, {})
    assert result == {}

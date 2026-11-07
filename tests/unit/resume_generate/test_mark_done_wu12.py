"""WU-12 mark_done node."""

from __future__ import annotations

from unittest.mock import patch

from jd_agent.graphs.resume_generate.nodes.mark_done.node import mark_done


def test_mark_done_publishes_end() -> None:
    with patch(
        "jd_agent.graphs.resume_generate.nodes.mark_done.node.publish_resume_generate_end_from_state",
    ) as publish:
        result = mark_done(
            {"session_id": "sess-1", "user_id": "user-1"},
            {"configurable": {"run_id": "run-2"}},
        )

    publish.assert_called_once()
    assert result == {}

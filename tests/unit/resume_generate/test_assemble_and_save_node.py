"""assemble_and_save publishes resume data instead of postgres writes."""

from __future__ import annotations

from unittest.mock import patch

from jd_agent.graphs.resume_generate.nodes.assemble_and_save.node import assemble_and_save


def test_assemble_and_save_publishes_data() -> None:
    state = {
        "session_id": "sess-1",
        "user_id": "user-1",
        "briefs": {
            "static": {"basics": {"name": "Ada"}, "skills": []},
            "instances": {},
            "skills_sources": {},
        },
        "allocation": {"instance_order": [], "resume_fit": 0.0},
        "generated": {},
        "summary": {"text": "", "claimed_terms": [], "claimed_numbers": []},
        "verification": {
            "coverage": {"weighted": 0.0, "must": {}, "nice": {}},
            "gap_report": [],
            "dropped_lines": [],
        },
        "demand": {"fit_profile": 0.0},
        "atoms": [],
        "repair_round": 0,
        "jd_context": {"unresolved": []},
    }
    with patch(
        "jd_agent.graphs.resume_generate.nodes.assemble_and_save.node.publish_resume_generate_data_from_state",
    ) as mock_publish:
        result = assemble_and_save(state, {"configurable": {"run_id": "run-1"}})

    mock_publish.assert_called_once()
    call = mock_publish.call_args
    assert call.kwargs["kind"] == "resume"
    assert isinstance(call.kwargs["data"]["resume"], dict)
    assert isinstance(call.kwargs["data"]["resume_trace"], dict)
    assert isinstance(call.kwargs["data"]["resume_date"], str)
    assert result["generate_status"] == "done"
    assert result["resume"] == call.kwargs["data"]["resume"]
    assert result["trace"] == call.kwargs["data"]["resume_trace"]

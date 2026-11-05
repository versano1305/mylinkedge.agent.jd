"""load_session against a fake postgres backend."""

from __future__ import annotations

import pytest
from conftest import JD_ID, SESSION_ID, USER_ID, FakeUserResumeBuilders, make_session

from jd_agent.graphs.gap_collect.nodes._legacy import load_session


def test_requires_session_id(fake_urb: FakeUserResumeBuilders) -> None:
    with pytest.raises(ValueError, match="session_id is required"):
        load_session({"session_id": "  "}, {})


def test_missing_session_raises(fake_urb: FakeUserResumeBuilders) -> None:
    with pytest.raises(ValueError, match="No user_resume_builder row"):
        load_session({"session_id": "missing"}, {})


def test_unextracted_jd_raises(fake_urb: FakeUserResumeBuilders) -> None:
    fake_urb.sessions[SESSION_ID] = make_session(extraction_status="extracting")
    with pytest.raises(ValueError, match="not extracted"):
        load_session({"session_id": SESSION_ID}, {})


def test_loads_session_and_jd(fake_urb: FakeUserResumeBuilders) -> None:
    result = load_session({"session_id": SESSION_ID}, {})

    assert result["user_id"] == USER_ID
    assert result["job_description_id"] == JD_ID
    assert result["session"].id == SESSION_ID
    assert result["jd"].id == JD_ID
    assert result["jd"].extraction_status == "done"

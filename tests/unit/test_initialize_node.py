"""Unit tests for the initialize node."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from jd_agent.graphs.jd_extract.nodes import initialize
from jd_agent.integrations.supabase.jd_repository import JobDescription


def _jd(**overrides: object) -> JobDescription:
    payload = {
        "id": "jd-1",
        "origin_type": "copy_paste",
        "origin_jd": "Pasted text",
        "company_name": "Acme",
        "title_name": "Engineer",
    }
    payload.update(overrides)
    return JobDescription.model_validate(payload)


def test_initialize_accepts_job_description() -> None:
    jd = _jd()
    state = {"jd": jd}
    config = {"configurable": {"run_id": "run-1"}}
    with patch(
        "jd_agent.graphs.jd_extract.nodes.initialize.node.publish_jd_extraction_start_from_state",
    ) as publish_start:
        result = initialize(state, config)

    assert result == {"jd": jd, "jd_id": "jd-1", "extraction_status": "extracting"}
    publish_start.assert_called_once()
    published_state, published_config = publish_start.call_args.args
    assert published_state["jd_id"] == "jd-1"
    assert published_state["jd"] is jd
    assert published_config is config


def test_initialize_accepts_jd_dict() -> None:
    raw = _jd().model_dump()
    with patch(
        "jd_agent.graphs.jd_extract.nodes.initialize.node.publish_jd_extraction_start_from_state",
    ):
        result = initialize({"jd": raw, "jd_id": "jd-1"}, {})

    assert result["jd_id"] == "jd-1"
    assert isinstance(result["jd"], JobDescription)
    assert result["jd"].origin_jd == "Pasted text"
    assert result["extraction_status"] == "extracting"


def test_initialize_missing_jd() -> None:
    with pytest.raises(ValueError, match="jd is required"):
        initialize({}, {})


def test_initialize_rejects_mismatched_jd_id() -> None:
    with pytest.raises(ValueError, match="does not match"):
        initialize({"jd": _jd(), "jd_id": "other"}, {})


def test_initialize_empty_origin_jd() -> None:
    with pytest.raises(ValueError, match="origin_jd is empty"):
        initialize({"jd": _jd(origin_jd="")}, {})


def test_initialize_unknown_origin_type() -> None:
    with pytest.raises(ValueError, match="Unknown origin_type"):
        initialize({"jd": _jd(origin_type="fax_machine")}, {})

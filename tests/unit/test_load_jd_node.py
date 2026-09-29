"""Unit tests for load_jd node."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from jd_agent.graphs.jd_extract.nodes import load_jd
from jd_agent.integrations.supabase.jd_repository import JobDescription


def test_load_jd_returns_row() -> None:
    row = JobDescription(
        id="jd-1",
        origin_type="copy_paste",
        origin_jd="Pasted text",
        company_name="Acme",
        title_name="Engineer",
    )
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.client_from_env",
            return_value=MagicMock(),
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.jd_repo.get_by_id",
            return_value=row,
        ),
    ):
        result = load_jd({"jd_id": "jd-1"}, {})

    assert result == {"jd": row}


def test_load_jd_missing_row() -> None:
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.client_from_env",
            return_value=MagicMock(),
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.jd_repo.get_by_id",
            return_value=None,
        ),
    ):
        with pytest.raises(ValueError, match="No job_description"):
            load_jd({"jd_id": "missing"}, {})


def test_load_jd_empty_origin_jd() -> None:
    row = JobDescription(id="jd-1", origin_type="copy_paste", origin_jd="")
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.client_from_env",
            return_value=MagicMock(),
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.jd_repo.get_by_id",
            return_value=row,
        ),
    ):
        with pytest.raises(ValueError, match="origin_jd is empty"):
            load_jd({"jd_id": "jd-1"}, {})


def test_load_jd_unknown_origin_type() -> None:
    row = JobDescription(
        id="jd-1",
        origin_type="fax_machine",
        origin_jd="something",
    )
    with (
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.client_from_env",
            return_value=MagicMock(),
        ),
        patch(
            "jd_agent.graphs.jd_extract.nodes._legacy.jd_repo.get_by_id",
            return_value=row,
        ),
    ):
        with pytest.raises(ValueError, match="Unknown origin_type"):
            load_jd({"jd_id": "jd-1"}, {})

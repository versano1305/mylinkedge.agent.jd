"""Live end-to-end invocation of the resume generate graph.

Requires (otherwise skipped):
- ``RUN_RESUME_GENERATE_INTEGRATION=1``
- ``SUPABASE_URL``, ``SUPABASE_SECRET_KEY``
- ``RESUME_GENERATE_TEST_SESSION_ID`` (existing ``user_resume_builder.id``)
- ``NEO4J_URI`` (skills graph + candidate dossier)

The test session must already exist with:
- a joined ``job_description`` whose ``extraction_status = 'done'``
- non-empty ``job_description.skills`` (run ``jd_extract`` first)
- ``user_id`` (= Neo4j ``ownerId``) with at most one ``Person`` node

Invoke with ``{"session_id": "<uuid>"}`` only — the minimum graph input.
LLM steps are still stubs (WU-09+); the run should finish with a schema-valid
empty ``resume`` and ``trace``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from jd_agent.graphs.resume_generate.models import ResumeTrace
from jd_agent.graphs.resume_generate.resume_generate_graph import graph
from mylinkedge_agent_tools.postgres import get_postgres_db

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")


def _integration_env_ready() -> bool:
    if os.getenv("RUN_RESUME_GENERATE_INTEGRATION", "").strip() != "1":
        return False
    required = (
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "RESUME_GENERATE_TEST_SESSION_ID",
        "NEO4J_URI",
    )
    return all(os.getenv(name, "").strip() for name in required)


pytestmark = pytest.mark.skipif(
    not _integration_env_ready(),
    reason=(
        "Set RUN_RESUME_GENERATE_INTEGRATION=1 plus SUPABASE_URL, "
        "SUPABASE_SECRET_KEY, RESUME_GENERATE_TEST_SESSION_ID, and NEO4J_URI"
    ),
)


def test_resume_generate_graph_live_minimum_invoke() -> None:
    """Invoke the full graph with session_id only; assert done + schema-valid output."""
    session_id = os.environ["RESUME_GENERATE_TEST_SESSION_ID"].strip()

    result = graph.invoke({"session_id": session_id})

    assert result.get("generate_status") == "done"
    assert isinstance(result.get("user_id"), str) and result["user_id"].strip()

    resume = result.get("resume")
    assert isinstance(resume, dict)
    assert str(resume.get("$schema", "")).endswith("schema.json")
    assert "basics" in resume

    trace = ResumeTrace.model_validate(result.get("trace"))
    assert trace.schema_version == 1
    assert trace.meta.user_id == result["user_id"]

    dossier = result.get("dossier")
    assert isinstance(dossier, dict)
    assert dossier.get("user_id") == result["user_id"]

    jd_targets = result.get("jd_targets")
    assert isinstance(jd_targets, list)
    assert jd_targets, "test session JD must have extracted skills"

    demand = result.get("demand")
    assert isinstance(demand, dict)
    assert isinstance(demand.get("fit_profile"), (int, float))
    assert demand.get("d_star")
    assert demand.get("edges_subset") is not None

    row = get_postgres_db().user_resume_builders.get_by_id(session_id)
    assert row is not None
    assert row.status == "generate"
    assert isinstance(row.resume, dict)
    assert row.resume.get("$schema", "").endswith("schema.json")
    assert isinstance(row.resume_trace, dict)

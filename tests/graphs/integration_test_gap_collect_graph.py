"""Live end-to-end invocation of the gap collect graph.

Requires (otherwise skipped):
- ``RUN_GAP_COLLECT_INTEGRATION=1``
- ``SUPABASE_URL``, ``SUPABASE_SECRET_KEY``
- ``GAP_COLLECT_TEST_SESSION_ID`` (existing ``user_resume_builder.id``)
- ``NEO4J_URI`` (skills graph + candidate held skills)

The test session must already exist with:
- a joined ``job_description`` whose ``extraction_status = 'done'``
- non-empty ``job_description.skills`` (run ``jd_extract`` first)
- ``user_id`` that has at least some Skill evidence in Neo4j (empty held
  set still runs, but Fit / Latent will be uninteresting)

Invoke with ``{session_id}`` only. The session row is updated in place:
``status`` → ``gap-interview``, ``gaps`` / ``gaps_date`` written.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from jd_agent.graphs.gap_collect.gap_collect_graph import graph
from jd_agent.integrations.supabase import (
    user_resume_builder_repository as urb_repo,
)
from jd_agent.integrations.supabase.client import client_from_env

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")


def _integration_env_ready() -> bool:
    if os.getenv("RUN_GAP_COLLECT_INTEGRATION", "").strip() != "1":
        return False
    required = (
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "GAP_COLLECT_TEST_SESSION_ID",
        "NEO4J_URI",
    )
    return all(os.getenv(name, "").strip() for name in required)


pytestmark = pytest.mark.skipif(
    not _integration_env_ready(),
    reason=(
        "Set RUN_GAP_COLLECT_INTEGRATION=1 plus SUPABASE_URL, "
        "SUPABASE_SECRET_KEY, GAP_COLLECT_TEST_SESSION_ID, and NEO4J_URI"
    ),
)


def test_gap_collect_graph_live_ends_done() -> None:
    """Invoke the full graph by session_id; assert gaps persisted and status advanced."""
    session_id = os.environ["GAP_COLLECT_TEST_SESSION_ID"].strip()

    result = graph.invoke({"session_id": session_id})

    assert result.get("gap_status") == "done"
    gaps = result.get("gaps")
    assert isinstance(gaps, dict)
    assert gaps.get("schema_version") == 1
    assert "meta" in gaps and "review" in gaps and "skills" in gaps
    assert "interview" in gaps
    assert isinstance(gaps["meta"].get("fit"), (int, float))
    assert set(gaps["meta"].get("zone_counts") or {}) >= {
        "confirmed",
        "latent",
        "true_gap",
    }
    assert isinstance(gaps["interview"].get("queue"), list)

    # Round-trip: the session row itself must reflect the write.
    client = client_from_env()
    row = urb_repo.get_by_id(client, session_id)
    assert row is not None
    assert row.status == urb_repo.GAP_INTERVIEW_STEP
    assert row.gaps_date is not None
    assert isinstance(row.gaps, dict)
    assert row.gaps.get("schema_version") == 1
    assert row.gaps.get("meta", {}).get("fit") == gaps["meta"]["fit"]

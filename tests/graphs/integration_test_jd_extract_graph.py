"""Live end-to-end invocation of the JD extract graph.

Requires (otherwise skipped):
- ``RUN_JD_EXTRACT_INTEGRATION=1``
- ``SUPABASE_URL``, ``SUPABASE_SECRET_KEY``
- ``JD_EXTRACT_TEST_JD_ID`` (existing ``job_description.id``)
- ``OPENAI_API_KEY``

The test row must already exist with:
- ``origin_type = 'copy_paste'``
- ``origin_jd`` = non-empty pasted JD text
- ``company_name`` / ``title_name`` set (paste path)

Invoke with ``{jd_id}`` only; the graph loads origin fields from the DB
using ``SUPABASE_*`` env vars. The row will be updated in place.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from jd_agent.graphs.jd_extract.jd_extract_graph import graph

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")


def _integration_env_ready() -> bool:
    if os.getenv("RUN_JD_EXTRACT_INTEGRATION", "").strip() != "1":
        return False
    required = (
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "JD_EXTRACT_TEST_JD_ID",
        "LITELLM_MASTER_KEY",
        "LITELLM_API_BASE",
    )
    return all(os.getenv(name, "").strip() for name in required)


pytestmark = pytest.mark.skipif(
    not _integration_env_ready(),
    reason=(
        "Set RUN_JD_EXTRACT_INTEGRATION=1 plus SUPABASE_URL, "
        "SUPABASE_SECRET_KEY, JD_EXTRACT_TEST_JD_ID, and OPENAI_API_KEY"
    ),
)


def test_jd_extract_graph_live_raw_ends_done() -> None:
    """Invoke the full graph by jd_id; assert final extraction_status is done."""
    jd_id = os.environ["JD_EXTRACT_TEST_JD_ID"].strip()

    result = graph.invoke({"jd_id": jd_id})

    assert result["extraction_status"] == "done"

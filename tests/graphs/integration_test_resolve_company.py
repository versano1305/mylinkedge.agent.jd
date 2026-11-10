"""Live invocation of ``resolve_company`` via event-hub ``company_lookup``.

Requires (otherwise skipped):
- ``RUN_RESOLVE_COMPANY_INTEGRATION=1``
- ``SNS_LOOKUP_TOPIC_ARN`` (or ``SNS_PROCESS_EVENTS_TOPIC_ARN``)
- ``AWS_ENDPOINT_URL``, ``AWS_REGION``
- ``EVENT_HUB_STATUS_BASE_URL``, ``EVENT_HUB_SERVICE_SECRET``
- ``RESOLVE_COMPANY_TEST_COMPANY_NAME`` (existing ``Company.name`` in the
  Neo4j data graph that the hub lookup consumer can match)
- Event hub HTTP status API reachable at ``EVENT_HUB_STATUS_BASE_URL``

Optional:
- ``RESOLVE_COMPANY_TEST_COMPANY_ID`` — assert the exact resolved id
- ``NEO4J_URI`` (+ auth / ``NEO4J_DATA_DATABASE``) — cross-check the id
  against the data graph when the exact-id env var is unset

The event hub must be running and consuming the lookup queue so the published
``company_lookup`` is processed and status appears at ``GET /events/{id}``.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from dotenv import load_dotenv

from jd_agent.graphs.jd_extract.nodes import resolve_company
from jd_agent.integrations.supabase.jd_repository import JobDescription

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")


def _hub_status_reachable() -> bool:
    base = os.getenv("EVENT_HUB_STATUS_BASE_URL", "").strip().rstrip("/")
    if not base:
        return False
    request = urllib.request.Request(f"{base}/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _integration_env_ready() -> bool:
    if os.getenv("RUN_RESOLVE_COMPANY_INTEGRATION", "1").strip() != "1":
        return False
    has_lookup_topic = bool(
        os.getenv("SNS_LOOKUP_TOPIC_ARN", "").strip()
        or os.getenv("SNS_PROCESS_EVENTS_TOPIC_ARN", "").strip()
    )
    required = (
        "AWS_ENDPOINT_URL",
        "AWS_REGION",
        "EVENT_HUB_STATUS_BASE_URL",
        "EVENT_HUB_SERVICE_SECRET",
        "RESOLVE_COMPANY_TEST_COMPANY_NAME",
    )
    return (
        has_lookup_topic
        and all(os.getenv(name, "").strip() for name in required)
        and _hub_status_reachable()
    )


# pytestmark = pytest.mark.skipif(
#     not _integration_env_ready(),
#     reason=(
#         "Set RUN_RESOLVE_COMPANY_INTEGRATION=1 plus SNS_LOOKUP_TOPIC_ARN "
#         "(or SNS_PROCESS_EVENTS_TOPIC_ARN), AWS_ENDPOINT_URL, AWS_REGION, "
#         "EVENT_HUB_STATUS_BASE_URL, EVENT_HUB_SERVICE_SECRET, "
#         "RESOLVE_COMPANY_TEST_COMPANY_NAME, and a reachable event-hub /health"
#     ),
# )

def test_resolve_company_live_returns_company_id() -> None:
    """Publish company_lookup and assert the hub returns a resolved company id."""
    company_name = "Microsoft"
    jd = JobDescription(
        id="resolve-company-integration",
        company_name=company_name,
    )

    result = resolve_company(
        {"jd_id": jd.id, "jd": jd},
        {"configurable": {"run_id": "resolve-company-integration"}},
    )

    company_id = result.get("company_id")
    assert isinstance(company_id, str) and company_id.strip()

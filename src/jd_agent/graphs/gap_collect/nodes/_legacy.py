"""Session load, status markers, and persistence nodes.

Thin I/O nodes pending per-folder migration (mirrors ``jd_extract`` layout).
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.event_hub import (
    JdGapAnalysisFinish,
    JdGapAnalysisStarted,
    ProcessEventPublisher,
)

from jd_agent.graphs.gap_collect.state import GapCollectState
from jd_agent.integrations.supabase import (
    user_resume_builder_repository as urb_repo,
)
from jd_agent.integrations.supabase.client import client_from_env


def load_session(
    state: GapCollectState, config: RunnableConfig
) -> dict[str, Any]:
    """Load the resume-builder session and its joined job description."""
    _ = config
    session_id = str(state.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required")

    client = client_from_env()
    loaded = urb_repo.get_session_with_jd(client, session_id)
    if loaded is None:
        raise ValueError(f"No user_resume_builder row for id={session_id}")

    jd = loaded.job_description
    if jd.extraction_status != "done":
        raise ValueError(
            f"job_description {jd.id} is not extracted "
            f"(extraction_status={jd.extraction_status!r}); run jd_extract first"
        )

    return {
        "session": loaded.session,
        "jd": jd,
        "user_id": loaded.session.user_id,
        "job_description_id": loaded.session.job_description_id,
    }


def mark_analyzing(
    state: GapCollectState, config: RunnableConfig
) -> dict[str, Any]:
    """Mark gap analysis in progress and publish ``process.jd-gap-analysis/started``."""
    session_id = str(state.get("session_id") or "").strip()
    client = client_from_env()
    urb_repo.mark_gap_analysis_in_progress(client, session_id)
    job_description_id = str(state.get("job_description_id") or "")
    return _publish(
        state,
        JdGapAnalysisStarted(
            job_id=job_description_id,
            job_description_id=job_description_id,
            trace_id=_trace_id(config),
        ),
        error_label="jd-gap-analysis started",
        result={"gap_status": "analyzing"},
    )


def save_gaps(state: GapCollectState, config: RunnableConfig) -> dict[str, Any]:
    """Persist the gaps jsonb and advance the session to the gap-interview step."""
    _ = config
    session_id = str(state.get("session_id") or "").strip()
    gaps = dict(state.get("gaps") or {})
    if not gaps:
        raise ValueError("gaps must be computed before save_gaps")

    client = client_from_env()
    updated = urb_repo.save_gaps(client, session_id, gaps)
    return {"session": updated}


def mark_done(state: GapCollectState, config: RunnableConfig) -> dict[str, Any]:
    """Publish ``process.jd-gap-analysis/finish`` and mark the run done.

    Gaps are already persisted by ``save_gaps``. The library finish payload is
    empty; a transport failure is a soft error rather than a failed collection.
    """
    job_description_id = str(state.get("job_description_id") or "")
    return _publish(
        state,
        JdGapAnalysisFinish(
            job_id=job_description_id,
            job_description_id=job_description_id,
            trace_id=_trace_id(config),
        ),
        error_label="jd-gap-analysis finish",
        result={"gap_status": "done"},
    )


def _publish(
    state: GapCollectState,
    event: JdGapAnalysisStarted | JdGapAnalysisFinish,
    *,
    error_label: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    errors = list(state.get("errors") or [])
    try:
        ProcessEventPublisher().publish(event)
    except Exception as exc:  # noqa: BLE001 - event transport is best-effort here
        errors.append(f"{error_label} publish failed: {type(exc).__name__}")
    return {**result, "errors": errors}


def _trace_id(config: RunnableConfig) -> str | None:
    configurable = (config or {}).get("configurable") or {}
    raw = configurable.get("thread_id") or configurable.get("run_id")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None

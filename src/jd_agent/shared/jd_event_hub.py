"""Publish JD-agent lifecycle events (event hub) from graph nodes."""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.event_hub.contract import GraphId
from mylinkedge_agent_tools.event_hub.core.hub_publisher import HubPublisher
from mylinkedge_agent_tools.event_hub.lifecycle import (
    JdExtractionStart,
    JdExtractionStartPayload,
    JdGapAnalysisStart,
    JdGapAnalysisStartPayload,
    ResumeGenerateStart,
    ResumeGenerateStartPayload,
)

logger = logging.getLogger(__name__)


def _lifecycle_publish_enabled() -> bool:
    return os.getenv("JD_LIFECYCLE_EVENTS_ENABLED", "1").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _non_empty_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _run_id_from_config(config: RunnableConfig | None) -> str | None:
    if not isinstance(config, dict):
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None
    return _non_empty_str(configurable.get("run_id")) or _non_empty_str(
        configurable.get("thread_id")
    )


def publish_jd_extraction_start(
    *,
    job_description_id: str,
    job_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    jd_id = job_description_id.strip()
    if not jd_id:
        return
    resolved_job_id = (job_id or jd_id).strip() or jd_id
    try:
        HubPublisher().publish(
            JdExtractionStart(
                initiator=GraphId.JD_EXTRACT,
                user_id=_non_empty_str(user_id),
                payload=JdExtractionStartPayload(
                    job_id=resolved_job_id,
                    job_description_id=jd_id,
                    run_id=_non_empty_str(run_id),
                ),
            )
        )
    except Exception:
        logger.exception("Failed to publish jd_extraction_start for %s", jd_id)


def publish_jd_gap_analysis_start(
    *,
    job_description_id: str,
    job_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    jd_id = job_description_id.strip()
    if not jd_id:
        return
    resolved_job_id = (job_id or jd_id).strip() or jd_id
    try:
        HubPublisher().publish(
            JdGapAnalysisStart(
                initiator=GraphId.GAP_COLLECT,
                user_id=_non_empty_str(user_id),
                payload=JdGapAnalysisStartPayload(
                    job_id=resolved_job_id,
                    job_description_id=jd_id,
                    run_id=_non_empty_str(run_id),
                ),
            )
        )
    except Exception:
        logger.exception("Failed to publish jd_gap_analysis_start for %s", jd_id)


def publish_resume_generate_start(
    *,
    job_id: str,
    user_id: str | None = None,
    run_id: str | None = None,
) -> None:
    if not _lifecycle_publish_enabled():
        return
    resolved_job_id = job_id.strip()
    if not resolved_job_id:
        return
    try:
        HubPublisher().publish(
            ResumeGenerateStart(
                initiator=GraphId.RESUME_GENERATE,
                user_id=_non_empty_str(user_id),
                payload=ResumeGenerateStartPayload(
                    job_id=resolved_job_id,
                    run_id=_non_empty_str(run_id),
                ),
            )
        )
    except Exception:
        logger.exception(
            "Failed to publish resume_generate_start for %s", resolved_job_id
        )


def publish_jd_extraction_start_from_state(
    state: dict[str, Any],
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``jd_extraction_start`` from the first ``jd_extract`` node."""
    jd_id = _non_empty_str(state.get("jd_id"))
    if not jd_id:
        return
    publish_jd_extraction_start(
        job_description_id=jd_id,
        job_id=_non_empty_str(state.get("job_id")) or jd_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_jd_gap_analysis_start_from_state(
    state: dict[str, Any],
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``jd_gap_analysis_start`` from the first ``gap_collect`` node."""
    jd_id = _non_empty_str(state.get("job_description_id"))
    session_id = _non_empty_str(state.get("session_id"))
    if not jd_id:
        return
    publish_jd_gap_analysis_start(
        job_description_id=jd_id,
        job_id=_non_empty_str(state.get("job_id")) or session_id or jd_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )


def publish_resume_generate_start_from_state(
    state: dict[str, Any],
    config: RunnableConfig | None = None,
) -> None:
    """Publish ``resume_generate_start`` from the first ``resume_generate`` node."""
    session_id = _non_empty_str(state.get("session_id"))
    job_id = _non_empty_str(state.get("job_id")) or session_id
    if not job_id:
        return
    publish_resume_generate_start(
        job_id=job_id,
        user_id=_non_empty_str(state.get("user_id")),
        run_id=_run_id_from_config(config),
    )

"""Publish ``RESUME_GENERATE_START`` for downstream status updates."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.shared.jd_event_hub import publish_resume_generate_start_from_state


def mark_generating(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Publish ``RESUME_GENERATE_START``."""

    publish_resume_generate_start_from_state(state, config)
    return {}

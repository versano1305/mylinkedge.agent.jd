"""Final node: publish ``RESUME_GENERATE_END`` after assembly."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.shared.jd_event_hub import publish_resume_generate_end_from_state


def mark_done(state: ResumeGenerateState, config: RunnableConfig) -> dict[str, Any]:
    """Publish ``RESUME_GENERATE_END``; resume payload is published from ``assemble_and_save``."""

    publish_resume_generate_end_from_state(state, config)
    return {}

"""Final node for the resume-generate graph (persistence handled upstream)."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.state import ResumeGenerateState


def mark_done(state: ResumeGenerateState, config: RunnableConfig) -> dict[str, Any]:
    """No-op terminal node; graph output is already persisted."""

    _ = config
    _ = state
    return {}

"""WU-10 — Generate ``basics.summary`` after highlights."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.feedback_keys import SUMMARY_FEEDBACK_KEY
from jd_agent.graphs.resume_generate.models import SummaryResult
from jd_agent.graphs.resume_generate.nodes.generate_summary.agent import (
    generate_summary_llm,
)
from jd_agent.graphs.resume_generate.nodes.generate_summary.context import (
    build_summary_context,
    has_summary_content,
)
from jd_agent.graphs.resume_generate.state import ResumeGenerateState


def _summary_repair_feedback(state: ResumeGenerateState) -> list[str] | None:
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return None
    feedback_map = verification.get("feedback")
    if not isinstance(feedback_map, dict):
        return None
    raw = feedback_map.get(SUMMARY_FEEDBACK_KEY)
    if isinstance(raw, list):
        messages = [str(m) for m in raw if str(m).strip()]
        return messages or None
    if raw:
        return [str(raw)]
    return None


def generate_summary(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    context = build_summary_context(state)
    if not has_summary_content(context):
        return {"summary": SummaryResult().model_dump()}

    repair_feedback = _summary_repair_feedback(state)
    result = generate_summary_llm(
        context,
        repair_feedback=repair_feedback,
        config=config,
    )
    return {"summary": result.model_dump()}

"""WU-09 — LLM highlight generation with parallel Send fan-out."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import Send

from jd_agent.graphs.resume_generate.models import (
    GeneratedInstance,
    InstanceBrief,
)
from jd_agent.graphs.resume_generate.nodes.generate_highlights.agent import (
    generate_for_brief,
)
from jd_agent.graphs.resume_generate.nodes.generate_highlights.dispatch import (
    build_highlight_sends,
)
from jd_agent.graphs.resume_generate.state import ResumeGenerateState


def dispatch_highlights_after_briefs(
    state: ResumeGenerateState,
) -> list[Send] | str:
    """Fan out one branch per generatable instance, or skip to summary."""
    sends = build_highlight_sends(state, from_repair=False)
    if not sends:
        return "generate_summary"
    return sends


def dispatch_highlights_after_verify(
    state: ResumeGenerateState,
) -> list[Send] | str:
    """Re-run failed instances only (WU-11); otherwise continue to assembly."""
    sends = build_highlight_sends(state, from_repair=True)
    if not sends:
        return "assemble_and_save"
    return sends


def generate_highlights(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Rewrite one instance brief into bullets; merges into ``generated`` via reducer.

    Pass LangGraph ``config`` through so nested ``create_agent`` / LLM runs stay on the
    parent graph trace (LangSmith), including parallel ``Send`` branches.

    Sync (not async): LangGraph Studio / sync ``invoke`` paths call Send workers via
    ``invoke``; async-only nodes raise TypeError there.
    """
    raw_brief = state.get("brief")
    if not isinstance(raw_brief, dict):
        raise ValueError("brief is required for generate_highlights")

    brief = InstanceBrief.model_validate(raw_brief)
    feedback_raw = state.get("feedback") or []
    feedback = (
        [str(m) for m in feedback_raw]
        if isinstance(feedback_raw, list)
        else [str(feedback_raw)]
    )

    if brief.budget <= 0 or not brief.atoms:
        payload = GeneratedInstance(summary="", highlights=[]).model_dump()
        return {"generated": {brief.instance_id: payload}}

    result = generate_for_brief(
        brief,
        repair_feedback=feedback or None,
        config=config,
    )
    payload = GeneratedInstance(
        summary=result.summary.strip(),
        highlights=result.highlights,
    ).model_dump()
    return {"generated": {brief.instance_id: payload}}

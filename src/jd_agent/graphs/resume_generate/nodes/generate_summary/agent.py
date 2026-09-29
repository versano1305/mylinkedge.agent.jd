"""LLM agent for ``basics.summary``."""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.constants import (
    BASICS_SUMMARY_IN_NODE_RETRIES,
    BASICS_SUMMARY_LLM_TEMPERATURE,
)
from jd_agent.graphs.resume_generate.models import SummaryResult
from jd_agent.graphs.resume_generate.nodes.generate_summary.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    build_user_message,
)
from jd_agent.graphs.resume_generate.nodes.generate_summary.validate import (
    validate_summary,
)
from jd_agent.shared.structured_llm import (
    build_structured_agent,
    invoke_structured_agent,
)

_AGENT: object | None = None


def _get_agent() -> object:
    global _AGENT
    if _AGENT is None:
        _AGENT = build_structured_agent(
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            response_format=SummaryResult,
            name="resume-basics-summary-generator",
            temperature=BASICS_SUMMARY_LLM_TEMPERATURE,
        )
    return _AGENT


def generate_summary_llm(
    context: dict[str, object],
    *,
    repair_feedback: list[str] | None = None,
    config: RunnableConfig | None = None,
) -> SummaryResult:
    agent = _get_agent()
    validation_errors: list[str] | None = None
    last: SummaryResult | None = None
    attempts = 1 + BASICS_SUMMARY_IN_NODE_RETRIES

    for _ in range(attempts):
        user_message = build_user_message(
            context,
            validation_errors=validation_errors,
            repair_feedback=repair_feedback if validation_errors is None else None,
        )
        last = invoke_structured_agent(agent, user_message, SummaryResult, config)
        validation_errors = validate_summary(context, last)
        if not validation_errors:
            return last

    assert last is not None
    joined = "; ".join(validation_errors or [])
    raise ValueError(f"basics summary failed validation: {joined}")

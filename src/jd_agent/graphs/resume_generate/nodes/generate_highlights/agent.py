"""LLM agent for one instance's highlights."""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.constants import (
    HIGHLIGHT_IN_NODE_RETRIES,
    HIGHLIGHT_LLM_TEMPERATURE,
)
from jd_agent.graphs.resume_generate.models import InstanceBrief
from jd_agent.graphs.resume_generate.nodes.generate_highlights.models import (
    HighlightGenerationResult,
)
from jd_agent.graphs.resume_generate.nodes.generate_highlights.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    build_user_message,
)
from jd_agent.graphs.resume_generate.nodes.generate_highlights.validate import (
    validate_generation,
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
            response_format=HighlightGenerationResult,
            name="resume-highlight-generator",
            temperature=HIGHLIGHT_LLM_TEMPERATURE,
        )
    return _AGENT


def generate_for_brief(
    brief: InstanceBrief,
    *,
    repair_feedback: list[str] | None = None,
    config: RunnableConfig | None = None,
) -> HighlightGenerationResult:
    """Call the LLM with validation-driven in-node retries."""
    agent = _get_agent()
    validation_errors: list[str] | None = None
    last_result: HighlightGenerationResult | None = None
    attempts = 1 + HIGHLIGHT_IN_NODE_RETRIES

    for _ in range(attempts):
        user_message = build_user_message(
            brief,
            validation_errors=validation_errors,
            repair_feedback=repair_feedback if validation_errors is None else None,
        )
        last_result = invoke_structured_agent(
            agent,
            user_message,
            HighlightGenerationResult,
            config,
        )
        validation_errors = validate_generation(brief, last_result)
        if not validation_errors:
            return last_result

    assert last_result is not None
    joined = "; ".join(validation_errors or [])
    raise ValueError(
        f"highlight generation failed validation for instance {brief.instance_id}: {joined}"
    )

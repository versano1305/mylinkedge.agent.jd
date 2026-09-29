"""Section skill extractor agent (``create_agent`` with structured response)."""

from __future__ import annotations

import os
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from jd_agent.graphs.jd_extract.nodes.extract_jd_info.models import (
    SectionSkillExtractionResult,
)

DEFAULT_MODEL = os.getenv("JD_LLM_MODEL", "openai:gpt-4o-mini")


def build_section_skill_agent(system_prompt: str) -> Any:
    """Build a skill-extractor agent with empty tools (extensible later).

    Pass tools here (e.g. taxonomy lookup, skill catalog search) when the
    resolve step needs in-agent tool calls rather than a separate LangGraph node.
    """
    model = ChatOpenAI(
        model="gpt-4o-mini",  # hardcoded; not "openai:..."
        base_url=os.getenv("LITELLM_API_BASE", "http://localhost:4000/v1"),
        api_key=os.getenv("LITELLM_MASTER_KEY", "sk-local-litellm"),
        temperature=0,
    )
    return create_agent(
        model=model,
        tools=[],
        system_prompt=system_prompt,
        response_format=SectionSkillExtractionResult,
        name="jd-section-skill-extractor",
    )


def invoke_section_skill_extractor(
    *,
    system_prompt: str,
    user_message: str,
    config: RunnableConfig | None = None,
) -> SectionSkillExtractionResult:
    """Run the skill-extractor agent and return structured ``SectionSkillExtractionResult``."""
    agent = build_section_skill_agent(system_prompt)
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config,
    )

    structured = result.get("structured_response") if isinstance(result, dict) else None
    if structured is None:
        raise ValueError("skill extractor did not return structured_response")
    if isinstance(structured, SectionSkillExtractionResult):
        return structured
    return SectionSkillExtractionResult.model_validate(structured)

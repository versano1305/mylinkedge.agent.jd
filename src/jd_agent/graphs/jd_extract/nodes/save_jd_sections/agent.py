"""JD section parser agent (``create_agent`` with structured response)."""

from __future__ import annotations

import os
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from jd_agent.graphs.jd_extract.nodes.save_jd_sections.models import (
    JDSectionParseResult,
)

DEFAULT_MODEL = os.getenv("JD_LLM_MODEL", "openai:gpt-4o-mini")


def build_section_parser_agent(system_prompt: str) -> Any:
    """Build a section-parser agent with empty tools (extensible later)."""
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
        response_format=JDSectionParseResult,
        name="jd-section-parser",
    )


def invoke_section_parser(
    *,
    system_prompt: str,
    user_message: str,
    config: RunnableConfig | None = None,
) -> JDSectionParseResult:
    """Run the section parser and return structured ``JDSectionParseResult``."""
    agent = build_section_parser_agent(system_prompt)
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config,
    )

    structured = result.get("structured_response") if isinstance(result, dict) else None
    if structured is None:
        raise ValueError("section parser did not return structured_response")
    if isinstance(structured, JDSectionParseResult):
        return structured
    return JDSectionParseResult.model_validate(structured)

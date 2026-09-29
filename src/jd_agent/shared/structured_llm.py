"""LiteLLM-backed structured agents shared across JD graphs."""

from __future__ import annotations

import os
from typing import Any, TypeVar

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def build_structured_agent(
    *,
    system_prompt: str,
    response_format: type[T],
    name: str,
    model: str | None = None,
    temperature: float = 0.2,
) -> Any:
    """Create a tool-less agent that returns ``response_format`` as structured output."""
    model_name = (model or os.getenv("RESUME_LLM_MODEL") or "gpt-4o-mini").strip()
    if model_name.startswith("openai:"):
        model_name = model_name.split(":", 1)[1]

    chat = ChatOpenAI(
        model=model_name,
        base_url=os.getenv("LITELLM_API_BASE", "http://localhost:4000/v1"),
        api_key=os.getenv("LITELLM_MASTER_KEY", "sk-local-litellm"),
        temperature=temperature,
    )
    return create_agent(
        model=chat,
        tools=[],
        system_prompt=system_prompt,
        response_format=response_format,
        name=name,
    )


def invoke_structured_agent(
    agent: Any,
    user_message: str,
    response_format: type[T],
    config: RunnableConfig | None = None,
) -> T:
    """Run an agent and coerce ``structured_response`` to ``response_format``."""
    result = agent.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config,
    )
    structured = result.get("structured_response") if isinstance(result, dict) else None
    if structured is None:
        raise ValueError("structured agent did not return structured_response")
    if isinstance(structured, response_format):
        return structured
    return response_format.model_validate(structured)

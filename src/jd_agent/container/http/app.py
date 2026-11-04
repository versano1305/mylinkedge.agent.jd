"""FastAPI app exposing ``/threads`` for JD agent graphs."""

from __future__ import annotations

from functools import lru_cache

from mylinkedge_agent_tools.langgraph_streaming.http import HttpSettings, create_app

from jd_agent.container.graph_registry import build_graph_registry


@lru_cache(maxsize=1)
def build_app():
    """Compiled FastAPI application."""
    return create_app(build_graph_registry(), HttpSettings.from_env())

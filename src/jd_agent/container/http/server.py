"""Run the HTTP container with uvicorn."""

from __future__ import annotations

import os

import uvicorn

from jd_agent.container.http.app import build_app

DEFAULT_HTTP_HOST = "0.0.0.0"
DEFAULT_HTTP_PORT = 8080


def serve() -> None:
    host = os.getenv("HTTP_HOST", DEFAULT_HTTP_HOST)
    port = int(os.getenv("HTTP_PORT", str(DEFAULT_HTTP_PORT)))
    uvicorn.run(build_app(), host=host, port=port)

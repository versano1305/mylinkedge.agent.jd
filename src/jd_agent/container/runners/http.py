"""HTTP container host: thread seeding and SSE streaming."""

from __future__ import annotations

from jd_agent.container.http.server import serve


class HttpContainerRunner:
    """Run the LangGraph thread HTTP API until shutdown."""

    def run(self) -> None:
        serve()

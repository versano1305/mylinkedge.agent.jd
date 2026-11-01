"""gRPC container host: ``GraphTurnService`` for ``jd_extract`` and ``gap_collect``."""

from __future__ import annotations

import os

from mylinkedge_agent_tools.langgraph_streaming.grpc.server import run_server

from jd_agent.container.graph_registry import build_graph_registry


class GrpcContainerRunner:
    """Run the LangGraph turn-streaming gRPC server."""

    def run(self) -> None:
        host = os.getenv("GRPC_HOST", "[::]")
        port = int(os.getenv("GRPC_PORT", "50051"))
        enable_reflection = os.getenv("GRPC_REFLECTION", "").lower() in (
            "1",
            "true",
            "yes",
        )
        run_server(
            build_graph_registry(),
            host=host,
            port=port,
            enable_health=True,
            enable_reflection=enable_reflection,
        )

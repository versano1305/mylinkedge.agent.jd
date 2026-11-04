"""gRPC container host: ``GraphTurnService`` for ``jd_extract`` and ``gap_collect``."""

from __future__ import annotations

import asyncio
import os

from mylinkedge_agent_tools.langgraph_streaming.grpc.server import serve

from jd_agent.container.graph_registry import build_graph_registry

DEFAULT_GRPC_HOST = "[::]"
DEFAULT_GRPC_PORT = 50051


def _listen_address(host: str, port: int) -> str:
    return f"{host}:{port}"


class GrpcContainerRunner:
    """Run the LangGraph turn-streaming gRPC server."""

    def run(self) -> None:
        host = os.getenv("GRPC_HOST", DEFAULT_GRPC_HOST)
        port = int(os.getenv("GRPC_PORT", str(DEFAULT_GRPC_PORT)))
        enable_reflection = os.getenv("GRPC_REFLECTION", "").lower() in (
            "1",
            "true",
            "yes",
        )
        listen_addr = _listen_address(host, port)

        async def _main() -> None:
            server = await serve(
                build_graph_registry(),
                host=host,
                port=port,
                enable_health=True,
                enable_reflection=enable_reflection,
            )
            print(f"gRPC server is up on {listen_addr} (port {port})", flush=True)
            await server.wait_for_termination()

        asyncio.run(_main())

"""gRPC container host startup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from jd_agent.container.runners.grpc import GrpcContainerRunner, _listen_address


def test_listen_address_includes_host_and_port() -> None:
    assert _listen_address("[::]", 50051) == "[::]:50051"


def test_grpc_runner_prints_when_server_is_up(capsys, monkeypatch) -> None:
    monkeypatch.setenv("GRPC_HOST", "127.0.0.1")
    monkeypatch.setenv("GRPC_PORT", "50052")
    server = AsyncMock()
    server.wait_for_termination = AsyncMock()

    with (
        patch(
            "jd_agent.container.runners.grpc.build_graph_registry",
            return_value=object(),
        ),
        patch(
            "jd_agent.container.runners.grpc.serve",
            new=AsyncMock(return_value=server),
        ),
    ):
        GrpcContainerRunner().run()

    output = capsys.readouterr().out
    assert "gRPC server is up on 127.0.0.1:50052" in output
    assert "port 50052" in output
    server.wait_for_termination.assert_awaited_once()

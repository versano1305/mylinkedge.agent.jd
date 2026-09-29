"""Container kind selection."""

from __future__ import annotations

import pytest

from jd_agent.container.registry import create_runner
from jd_agent.container.runners.grpc import GrpcContainerRunner
from jd_agent.container.runners.http import HttpContainerRunner
from jd_agent.container.runners.sqs.worker import SqsContainerRunner


def test_sqs_is_the_implemented_runner() -> None:
    assert isinstance(create_runner("sqs"), SqsContainerRunner)


def test_http_and_grpc_are_reserved() -> None:
    with pytest.raises(NotImplementedError, match="HTTP"):
        create_runner("http").run()
    with pytest.raises(NotImplementedError, match="gRPC"):
        create_runner("grpc").run()
    assert isinstance(create_runner("http"), HttpContainerRunner)
    assert isinstance(create_runner("grpc"), GrpcContainerRunner)


def test_unknown_container_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown container"):
        create_runner("websocket")

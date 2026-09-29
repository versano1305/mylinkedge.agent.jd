"""Select which container host to run."""

from __future__ import annotations

from enum import StrEnum

from jd_agent.container.runners.base import ContainerRunner


class ContainerKind(StrEnum):
    """Supported process hosts. Only ``sqs`` is implemented."""

    SQS = "sqs"
    HTTP = "http"
    GRPC = "grpc"


def create_runner(kind: str) -> ContainerRunner:
    """Build the runner named by ``--container``."""

    try:
        parsed = ContainerKind(kind)
    except ValueError as exc:
        raise ValueError(f"unknown container {kind!r}") from exc

    if parsed is ContainerKind.SQS:
        from jd_agent.container.runners.sqs.worker import SqsContainerRunner

        return SqsContainerRunner()
    if parsed is ContainerKind.HTTP:
        from jd_agent.container.runners.http import HttpContainerRunner

        return HttpContainerRunner()
    if parsed is ContainerKind.GRPC:
        from jd_agent.container.runners.grpc import GrpcContainerRunner

        return GrpcContainerRunner()
    raise ValueError(f"unknown container {kind!r}")

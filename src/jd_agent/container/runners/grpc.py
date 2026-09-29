"""gRPC host placeholder."""

from __future__ import annotations


class GrpcContainerRunner:
    """Reserved for a future gRPC server that invokes the same graphs."""

    def run(self) -> None:
        raise NotImplementedError(
            "gRPC container is not implemented yet. Use --container sqs."
        )

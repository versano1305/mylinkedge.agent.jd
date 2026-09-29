"""HTTP host placeholder."""

from __future__ import annotations


class HttpContainerRunner:
    """Reserved for a future HTTP server that invokes the same graphs."""

    def run(self) -> None:
        raise NotImplementedError(
            "HTTP container is not implemented yet. Use --container sqs."
        )

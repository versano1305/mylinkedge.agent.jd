"""Shared contract for a process host."""

from __future__ import annotations

from typing import Protocol


class ContainerRunner(Protocol):
    """One way to host the graphs (SQS, HTTP, gRPC, …)."""

    def run(self) -> None:
        """Block until the host stops."""

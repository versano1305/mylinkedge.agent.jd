"""SQS host for queued JD-agent work."""

from __future__ import annotations

import os

from mylinkedge_agent_tools.event_hub import EventConsumer, ProcessEventConsumer

from jd_agent.container.graph_invoke import GraphInvoker
from jd_agent.container.runners.sqs.handlers import AgentJdQueuedHandlers

DEFAULT_QUEUE_NAME = "skills-ai-local-agent-jd-events"


class AgentJdProcessConsumer(AgentJdQueuedHandlers, ProcessEventConsumer):
    """Long-poll ``agent-jd-events`` and run the matching graph."""

    QUEUE_NAME = DEFAULT_QUEUE_NAME

    def __init__(
        self,
        consumer: EventConsumer | None = None,
        *,
        invoker: GraphInvoker | None = None,
    ) -> None:
        self._invoker = invoker or GraphInvoker()
        super().__init__(consumer)

    def _queue_name(self) -> str:
        override = os.getenv("SQS_QUEUE_NAME", "").strip()
        if override:
            return override
        return super()._queue_name()


class SqsContainerRunner:
    """Block on the agent.jd SQS consumer until shutdown."""

    def run(self) -> None:
        AgentJdProcessConsumer().run()

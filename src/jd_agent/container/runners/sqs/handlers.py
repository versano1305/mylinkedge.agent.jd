"""SQS handlers that turn queued process events into graph runs."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mylinkedge_agent_tools.event_hub import (
    EventMessageContext,
    HandlerPermanentError,
    HandlerRetryError,
    JdExtractionQueued,
    JdGapAnalysisQueued,
    ResumeGenerateQueued,
    on,
)

from jd_agent.container.graph_invoke import GraphInvoker
from jd_agent.container.queued_inputs import (
    GAP_COLLECT_GRAPH,
    JD_EXTRACT_GRAPH,
    RESUME_GENERATE_GRAPH,
    gap_analysis_input,
    jd_extraction_input,
    resume_generate_input,
    thread_id_for,
)

logger = logging.getLogger(__name__)


class AgentJdQueuedHandlers:
    """Registered ``queued`` handlers for the agent.jd queue."""

    _invoker: GraphInvoker

    @on(JdExtractionQueued)
    async def handle_jd_extraction(
        self, event: JdExtractionQueued, ctx: EventMessageContext
    ) -> None:
        _ = ctx
        await self._run(JD_EXTRACT_GRAPH, jd_extraction_input(event), event)

    @on(JdGapAnalysisQueued)
    async def handle_gap_analysis(
        self, event: JdGapAnalysisQueued, ctx: EventMessageContext
    ) -> None:
        _ = ctx
        await self._run(GAP_COLLECT_GRAPH, gap_analysis_input(event), event)

    @on(ResumeGenerateQueued)
    async def handle_resume_generate(
        self, event: ResumeGenerateQueued, ctx: EventMessageContext
    ) -> None:
        _ = ctx
        await self._run(RESUME_GENERATE_GRAPH, resume_generate_input(event), event)

    async def _run(
        self,
        graph_id: str,
        graph_input: dict[str, Any],
        event: JdExtractionQueued | JdGapAnalysisQueued | ResumeGenerateQueued,
    ) -> None:
        try:
            await self._invoker.invoke(
                graph_id,
                graph_input,
                thread_id=thread_id_for(event),
            )
        except HandlerPermanentError:
            raise
        except HandlerRetryError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("graph %s failed for job_id=%s", graph_id, event.job_id)
            raise HandlerRetryError(str(exc)) from exc

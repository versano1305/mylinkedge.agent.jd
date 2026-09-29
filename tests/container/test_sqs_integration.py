"""Optional LocalStack smoke check for the agent.jd queue.

Skipped unless ``RUN_AGENT_JD_SQS_INTEGRATION=1`` and the SQS env vars from
``.env.example`` point at a deployed queue.
"""

from __future__ import annotations

import os

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from jd_agent.container.runners.sqs.worker import AgentJdProcessConsumer


def _enabled() -> bool:
    if os.getenv("RUN_AGENT_JD_SQS_INTEGRATION", "").strip() != "1":
        return False
    return bool(os.getenv("SQS_QUEUE_URL_PREFIX", "").strip())


pytestmark = pytest.mark.skipif(
    not _enabled(),
    reason="Set RUN_AGENT_JD_SQS_INTEGRATION=1 and SQS_QUEUE_URL_PREFIX",
)


def test_agent_jd_queue_exists() -> None:
    from unittest.mock import MagicMock

    from mylinkedge_agent_tools.event_hub.aws.consumer_settings import (
        AwsEventHubConsumerSettings,
    )
    from mylinkedge_agent_tools.event_hub.aws.settings import EventHubConfigurationError
    from mylinkedge_agent_tools.event_hub.aws.sqs_consumer import SqsEventConsumer

    worker = AgentJdProcessConsumer(consumer=MagicMock(), invoker=MagicMock())
    try:
        settings = AwsEventHubConsumerSettings.from_env()
        consumer = SqsEventConsumer(
            settings=settings,
            queue_url=settings.queue_url(worker._queue_name()),
        )
        consumer._client.get_queue_attributes(
            QueueUrl=consumer.queue_url,
            AttributeNames=["QueueArn"],
        )
    except EventHubConfigurationError as exc:
        pytest.skip(f"SQS not configured: {exc}")
    except (BotoCoreError, ClientError, OSError) as exc:
        pytest.skip(f"AWS SQS unavailable: {exc}")

import asyncio
from uuid import uuid4

import pytest
from common.queue import JobEnvelope

from .contract_test_queue import QueueBackend, QueueContract, consuming

pytestmark = pytest.mark.integration


class TestCeleryQueue(QueueContract):
    pass


@pytest.mark.asyncio
async def test_handler_runs_on_callers_event_loop(queue_backend: QueueBackend) -> None:
    loop = asyncio.get_running_loop()
    received = asyncio.Event()

    async def handler(envelope: JobEnvelope) -> None:
        assert asyncio.get_running_loop() is loop
        received.set()

    queue = f"event-loop-{uuid4()}"
    async with consuming(queue_backend.consumer, queue, handler):
        await queue_backend.producer.enqueue("review", {}, queue=queue)
        async with asyncio.timeout(20):
            await received.wait()

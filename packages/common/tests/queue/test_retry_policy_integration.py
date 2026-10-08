import asyncio
from time import monotonic
from uuid import uuid4

import pytest
from common.queue import JobEnvelope
from common.queue.backends.celery import CeleryQueueConsumer, CeleryQueueProducer
from common.queue.config import QueueSettings

from .contract_test_queue import consuming

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize(("max_attempts", "failures"), [(1, 0), (3, 2), (1, 1), (3, 3)])
async def test_configured_retry_limit_and_backoff(
    redis_url: str, max_attempts: int, failures: int
) -> None:
    settings = QueueSettings(
        broker_url=redis_url, max_attempts=max_attempts, backoff_base=0.2
    )
    producer = CeleryQueueProducer(settings)
    consumer = CeleryQueueConsumer(settings)
    queue = f"retry-{uuid4()}"
    attempts: list[JobEnvelope] = []
    timestamps: list[float] = []
    succeeded = asyncio.Event()
    dead_letters: asyncio.Queue[JobEnvelope] = asyncio.Queue()

    async def handler(envelope: JobEnvelope) -> None:
        attempts.append(envelope)
        timestamps.append(monotonic())
        if len(attempts) <= failures:
            raise RuntimeError("transient failure")
        succeeded.set()

    async with (
        consuming(consumer, queue, handler),
        consuming(consumer, f"{queue}.dead-letter", dead_letters.put),
    ):
        job_id = await producer.enqueue("review", {"unchanged": True}, queue=queue)
        async with asyncio.timeout(20):
            if failures == max_attempts:
                assert await dead_letters.get() == attempts[-1]
                assert not succeeded.is_set()
            else:
                await succeeded.wait()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(
                dead_letters.get(),
                timeout=settings.retry_delay(max_attempts) + 0.3,
            )

    assert [envelope.attempt for envelope in attempts] == list(
        range(1, min(failures + 1, max_attempts) + 1)
    )
    assert {envelope.job_id for envelope in attempts} == {job_id}
    for index in range(1, len(timestamps)):
        assert timestamps[index] - timestamps[index - 1] >= (
            settings.backoff_base * 2 ** (index - 1) * 0.95
        )


@pytest.mark.asyncio
async def test_handler_timeout_error_is_retried(redis_url: str) -> None:
    settings = QueueSettings(broker_url=redis_url, max_attempts=2, backoff_base=0)
    producer = CeleryQueueProducer(settings)
    consumer = CeleryQueueConsumer(settings)
    queue = f"timeout-{uuid4()}"
    attempts: list[int] = []
    succeeded = asyncio.Event()

    async def handler(envelope: JobEnvelope) -> None:
        attempts.append(envelope.attempt)
        if envelope.attempt == 1:
            raise TimeoutError("upstream timed out")
        succeeded.set()

    async with consuming(consumer, queue, handler):
        await producer.enqueue("review", {}, queue=queue)
        async with asyncio.timeout(20):
            await succeeded.wait()
    assert attempts == [1, 2]

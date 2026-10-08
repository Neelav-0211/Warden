import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from common.queue import JobEnvelope, JobHandler, QueueConsumer, QueueProducer


@dataclass
class QueueBackend:
    producer: QueueProducer
    consumer: QueueConsumer
    max_attempts: int
    backoff_base: float


@asynccontextmanager
async def consuming(
    consumer: QueueConsumer, queue: str, handler: JobHandler
) -> AsyncIterator[None]:
    task = asyncio.create_task(consumer.consume(queue, handler))
    try:
        yield
    finally:
        task.cancel()
        result = await asyncio.gather(task, return_exceptions=True)
        if isinstance(result[0], BaseException) and not isinstance(
            result[0], asyncio.CancelledError
        ):
            raise result[0]


class QueueContract:
    @pytest.mark.asyncio
    async def test_delivers_original_envelope(
        self, queue_backend: QueueBackend
    ) -> None:
        queue = f"delivery-{uuid4()}"
        payload = {"repository": "owner/repo", "nested": [None, True, {"count": 3}]}
        received: asyncio.Queue[JobEnvelope] = asyncio.Queue()
        before = datetime.now(UTC)
        job_id = await queue_backend.producer.enqueue("review", payload, queue=queue)
        other_id = await queue_backend.producer.enqueue("review", {}, queue=queue)
        assert job_id != other_id
        async with consuming(queue_backend.consumer, queue, received.put):
            async with asyncio.timeout(20):
                envelope = await received.get()
                other = await received.get()
        assert envelope.job_id == job_id
        assert envelope.job_type == "review"
        assert envelope.payload == payload
        assert before <= envelope.enqueued_at <= datetime.now(UTC)
        assert envelope.attempt == 1
        assert other.job_id == other_id

    @pytest.mark.asyncio
    async def test_exhausted_job_is_dead_lettered(
        self, queue_backend: QueueBackend
    ) -> None:
        queue = f"exhausted-{uuid4()}"
        attempts: list[JobEnvelope] = []
        dead_letters: asyncio.Queue[JobEnvelope] = asyncio.Queue()

        async def fail(envelope: JobEnvelope) -> None:
            attempts.append(envelope)
            raise RuntimeError("handler failed")

        async with (
            consuming(queue_backend.consumer, queue, fail),
            consuming(queue_backend.consumer, f"{queue}.dead-letter", dead_letters.put),
        ):
            job_id = await queue_backend.producer.enqueue(
                "review", {"keep": "payload"}, queue=queue
            )
            async with asyncio.timeout(20):
                dead_letter = await dead_letters.get()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(
                    dead_letters.get(),
                    timeout=queue_backend.backoff_base * 2**queue_backend.max_attempts
                    + 0.2,
                )

        assert [envelope.attempt for envelope in attempts] == list(
            range(1, queue_backend.max_attempts + 1)
        )
        assert {envelope.job_id for envelope in attempts} == {job_id}
        assert dead_letter == attempts[-1]
        assert dead_letter.payload == {"keep": "payload"}
        assert len({envelope.enqueued_at for envelope in attempts}) == 1

    @pytest.mark.asyncio
    async def test_named_queues_do_not_cross_deliver(
        self, queue_backend: QueueBackend
    ) -> None:
        review_queue = f"review-{uuid4()}"
        coding_queue = f"coding-{uuid4()}"
        reviews: asyncio.Queue[JobEnvelope] = asyncio.Queue()
        coding: asyncio.Queue[JobEnvelope] = asyncio.Queue()
        async with (
            consuming(queue_backend.consumer, review_queue, reviews.put),
            consuming(queue_backend.consumer, coding_queue, coding.put),
        ):
            expected_reviews = []
            expected_coding = []
            for index in range(3):
                expected_reviews.append(
                    await queue_backend.producer.enqueue(
                        "review", {"index": index}, queue=review_queue
                    )
                )
                expected_coding.append(
                    await queue_backend.producer.enqueue(
                        "code", {"index": index}, queue=coding_queue
                    )
                )
            async with asyncio.timeout(20):
                actual_reviews = [await reviews.get() for _ in range(3)]
                actual_coding = [await coding.get() for _ in range(3)]
        assert [envelope.job_id for envelope in actual_reviews] == expected_reviews
        assert [envelope.job_id for envelope in actual_coding] == expected_coding
        assert {envelope.job_type for envelope in actual_reviews} == {"review"}
        assert {envelope.job_type for envelope in actual_coding} == {"code"}

    @pytest.mark.asyncio
    async def test_cancelled_delivery_is_redelivered(
        self, queue_backend: QueueBackend
    ) -> None:
        queue = f"cancelled-{uuid4()}"
        started = asyncio.Event()
        cancelled = asyncio.Event()
        received: asyncio.Queue[JobEnvelope] = asyncio.Queue()

        async def blocked(envelope: JobEnvelope) -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async with consuming(queue_backend.consumer, queue, blocked):
            job_id = await queue_backend.producer.enqueue("review", {}, queue=queue)
            async with asyncio.timeout(20):
                await started.wait()
        assert cancelled.is_set()

        async with consuming(queue_backend.consumer, queue, received.put):
            async with asyncio.timeout(20):
                redelivered = await received.get()
        assert redelivered.job_id == job_id
        assert redelivered.attempt == 1

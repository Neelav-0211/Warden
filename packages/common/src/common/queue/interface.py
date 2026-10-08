from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from common.queue.envelope import JobEnvelope

JobHandler = Callable[[JobEnvelope], Awaitable[None]]


class QueueProducer(Protocol):
    """Publish JSON jobs for at-least-once delivery to a named queue.

    Handlers must be idempotent: a job may be delivered more than once.
    """

    async def enqueue(
        self, job_type: str, payload: dict[str, Any], *, queue: str
    ) -> str:
        """Return the stable job ID after publication, or raise on failure."""
        ...


class QueueConsumer(Protocol):
    """Consume one named queue with at-least-once delivery and bounded retries."""

    async def consume(self, queue: str, handler: JobHandler) -> None:
        """Run until cancelled, awaiting each handler before acknowledgement.

        Exceptions retry with an incremented attempt and configured backoff.
        Exhausted jobs retain their last envelope in ``<queue>.dead-letter``.
        Cancellation stops consumption and leaves unfinished work redeliverable.
        Queue names isolate delivery; consumers sharing a name compete for jobs.
        """
        ...

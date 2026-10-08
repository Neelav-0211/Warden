import asyncio
from concurrent.futures import CancelledError as FutureCancelledError
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from threading import Event
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from celery import Celery, Task
from celery.exceptions import Reject
from celery.utils.timer2 import Timer
from celery.worker.consumer import Consumer
from celery.worker.worker import WorkController
from kombu import Exchange, Queue

from common.logging import get_logger
from common.queue.config import QueueSettings, validate_queue_name
from common.queue.envelope import JobEnvelope
from common.queue.interface import JobHandler, QueueConsumer, QueueProducer

TASK_NAME = "warden.queue.deliver"
logger = get_logger(__name__)

if TYPE_CHECKING:
    DeliveryTaskBase = Task[[dict[str, Any]], None]
else:
    DeliveryTaskBase = Task


class QueueWorker(WorkController):
    consumer: Consumer


def _create_app(settings: QueueSettings, queue: str) -> Celery:
    app = Celery("warden.queue", broker=settings.broker_url, set_as_current=False)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        task_ignore_result=True,
        task_acks_late=True,
        task_acks_on_failure_or_timeout=False,
        task_reject_on_worker_lost=True,
        task_default_queue=queue,
        task_default_exchange=queue,
        task_default_routing_key=queue,
        task_queues=(Queue(queue, Exchange(queue, type="direct"), routing_key=queue),),
        task_create_missing_queues=True,
        worker_prefetch_multiplier=1,
        worker_enable_remote_control=False,
        worker_disable_rate_limits=True,
        broker_connection_timeout=5,
        broker_connection_max_retries=3,
        broker_transport_options={
            "visibility_timeout": settings.visibility_timeout,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
        },
        task_publish_retry=True,
        task_publish_retry_policy={
            "max_retries": 3,
            "interval_start": 0.2,
            "interval_step": 0.2,
            "interval_max": 1,
        },
    )
    return app


def _publish(app: Celery, envelope: JobEnvelope, queue: str) -> None:
    app.send_task(
        TASK_NAME,
        args=[envelope.model_dump(mode="json")],
        task_id=envelope.job_id,
        queue=queue,
        exchange=queue,
        routing_key=queue,
        ignore_result=True,
    )


class CeleryQueueProducer(QueueProducer):
    """Publish durable JSON Celery tasks without blocking the async caller."""

    def __init__(self, settings: QueueSettings) -> None:
        self.settings = settings

    async def enqueue(
        self, job_type: str, payload: dict[str, Any], *, queue: str
    ) -> str:
        validate_queue_name(queue)
        envelope = JobEnvelope(
            job_id=str(uuid4()),
            job_type=job_type,
            payload=payload,
            enqueued_at=datetime.now(UTC),
        )

        logger.info(
            "queue_publish_start",
            queue=queue,
            job_id=envelope.job_id,
            job_type=job_type,
            attempt=envelope.attempt,
        )

        def publish() -> None:
            with _create_app(self.settings, queue) as app:
                _publish(app, envelope, queue)

        try:
            await asyncio.to_thread(publish)
        except Exception:
            logger.exception(
                "queue_publish_failed",
                queue=queue,
                job_id=envelope.job_id,
                job_type=job_type,
            )
            raise

        logger.info(
            "queue_publish_succeeded",
            queue=queue,
            job_id=envelope.job_id,
            job_type=job_type,
        )
        return envelope.job_id


class CeleryQueueConsumer(QueueConsumer):
    """Run an isolated solo worker per consume call; handlers stay on its event loop.

    Each worker handles one job at a time. Scale with competing consumers.
    Cancelling consume rejects an unfinished delivery and joins the worker.
    """

    def __init__(self, settings: QueueSettings) -> None:
        self.settings = settings

    async def consume(self, queue: str, handler: JobHandler) -> None:
        validate_queue_name(queue)
        settings = self.settings
        loop = asyncio.get_running_loop()
        stopping = Event()
        app = _create_app(settings, queue)

        logger.info(
            "queue_consumer_starting",
            queue=queue,
            max_attempts=settings.max_attempts,
            visibility_timeout=settings.visibility_timeout,
        )

        class DeliveryTask(DeliveryTaskBase):
            name = TASK_NAME
            max_retries = settings.max_attempts - 1

            def run(self, data: dict[str, Any]) -> None:
                envelope = JobEnvelope.model_validate(data)
                logger.info(
                    "queue_delivery_received",
                    queue=queue,
                    job_id=envelope.job_id,
                    job_type=envelope.job_type,
                    attempt=envelope.attempt,
                )
                if stopping.is_set():
                    logger.info(
                        "queue_delivery_rejected_stopping",
                        queue=queue,
                        job_id=envelope.job_id,
                        attempt=envelope.attempt,
                    )
                    raise Reject("Consumer stopping", requeue=True)
                future = asyncio.run_coroutine_threadsafe(invoke(envelope), loop)
                try:
                    while True:
                        try:
                            future.result(timeout=0.1)
                            logger.info(
                                "queue_delivery_succeeded",
                                queue=queue,
                                job_id=envelope.job_id,
                                job_type=envelope.job_type,
                                attempt=envelope.attempt,
                            )
                            return
                        except FutureTimeoutError:
                            if future.done():
                                raise
                            if stopping.is_set():
                                future.cancel()
                                logger.info(
                                    "queue_delivery_cancelled_stopping",
                                    queue=queue,
                                    job_id=envelope.job_id,
                                    attempt=envelope.attempt,
                                )
                                raise Reject(
                                    "Consumer stopping", requeue=True
                                ) from None
                except FutureCancelledError as error:
                    logger.warning(
                        "queue_delivery_future_cancelled",
                        queue=queue,
                        job_id=envelope.job_id,
                        attempt=envelope.attempt,
                    )
                    raise Reject("Handler cancelled", requeue=True) from error
                except Reject:
                    raise
                except Exception as error:
                    if envelope.attempt >= settings.max_attempts:
                        dead_letter_queue = f"{queue}.dead-letter"
                        try:
                            _publish(app, envelope, dead_letter_queue)
                            logger.warning(
                                "queue_delivery_dead_lettered",
                                queue=queue,
                                dead_letter_queue=dead_letter_queue,
                                job_id=envelope.job_id,
                                job_type=envelope.job_type,
                                attempt=envelope.attempt,
                                error_type=type(error).__name__,
                            )
                        except Exception as publish_error:
                            logger.exception(
                                "queue_dead_letter_publish_failed",
                                queue=queue,
                                dead_letter_queue=dead_letter_queue,
                                job_id=envelope.job_id,
                                attempt=envelope.attempt,
                            )
                            raise Reject(
                                "Dead-letter publication failed", requeue=True
                            ) from publish_error
                        return
                    retried = envelope.model_copy(
                        update={"attempt": envelope.attempt + 1}
                    )
                    countdown = settings.retry_delay(envelope.attempt)
                    logger.warning(
                        "queue_delivery_retry_scheduled",
                        queue=queue,
                        job_id=envelope.job_id,
                        job_type=envelope.job_type,
                        attempt=envelope.attempt,
                        next_attempt=retried.attempt,
                        countdown_seconds=countdown,
                        error_type=type(error).__name__,
                    )
                    raise self.retry(
                        exc=error,
                        args=(retried.model_dump(mode="json"),),
                        countdown=countdown,
                        max_retries=settings.max_attempts - 1,
                        queue=queue,
                        exchange=queue,
                        routing_key=queue,
                    ) from error

        async def invoke(envelope: JobEnvelope) -> None:
            await handler(envelope)

        class AppTimer(Timer):
            def run(self) -> None:
                app.set_current()
                super().run()

        def build_worker() -> QueueWorker:
            app.set_current()
            app.register_task(DeliveryTask())
            return QueueWorker(
                app=app,
                pool="solo",
                concurrency=1,
                queues=[queue],
                hostname=f"warden-{uuid4()}@localhost",
                without_heartbeat=True,
                without_mingle=True,
                without_gossip=True,
                use_eventloop=False,
                timer_cls=AppTimer,
            )

        def start_worker(worker: QueueWorker) -> None:
            app.set_current()
            worker.start()

        build = asyncio.create_task(asyncio.to_thread(build_worker))
        running: asyncio.Task[None] | None = None
        try:
            worker = await asyncio.shield(build)
            logger.info("queue_consumer_started", queue=queue)
            running = asyncio.create_task(asyncio.to_thread(start_worker, worker))
            await asyncio.shield(running)
            logger.error("queue_consumer_stopped_unexpectedly", queue=queue)
            raise RuntimeError(f"Queue worker for {queue!r} stopped unexpectedly")
        finally:
            stopping.set()
            logger.info("queue_consumer_stopping", queue=queue)
            try:
                worker = await build
                if running is not None:
                    worker.consumer.call_soon(worker.stop)
                    await running
                else:
                    await asyncio.to_thread(worker.stop)
            finally:
                app.close()
                logger.info("queue_consumer_stopped", queue=queue)

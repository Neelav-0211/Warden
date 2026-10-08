from collections.abc import Iterator

import pytest
from common.queue.backends.celery import CeleryQueueConsumer, CeleryQueueProducer
from common.queue.config import QueueSettings
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from .contract_test_queue import QueueBackend


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    container = DockerContainer("redis:7-alpine").with_exposed_ports(6379)
    container.waiting_for(LogMessageWaitStrategy("Ready to accept connections"))
    with container as redis:
        yield f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"


@pytest.fixture(params=["celery"])
def queue_backend(request: pytest.FixtureRequest, redis_url: str) -> QueueBackend:
    assert request.param == "celery"
    settings = QueueSettings(broker_url=redis_url, max_attempts=3, backoff_base=0.1)
    return QueueBackend(
        producer=CeleryQueueProducer(settings),
        consumer=CeleryQueueConsumer(settings),
        max_attempts=settings.max_attempts,
        backoff_base=settings.backoff_base,
    )

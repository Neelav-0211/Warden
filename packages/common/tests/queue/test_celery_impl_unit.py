from unittest.mock import MagicMock, patch

import pytest
from common.queue import JobEnvelope
from common.queue.backends.celery import CeleryQueueProducer, _create_app
from common.queue.config import QueueSettings
from pydantic import ValidationError

pytestmark = pytest.mark.unit


@pytest.fixture
def settings() -> QueueSettings:
    return QueueSettings(broker_url="redis://localhost:6379/0")


def test_celery_delivery_configuration(settings: QueueSettings) -> None:
    with _create_app(settings, "reviews") as app:
        assert app.conf.task_acks_late is True
        assert app.conf.task_acks_on_failure_or_timeout is False
        assert app.conf.task_reject_on_worker_lost is True
        assert app.conf.task_serializer == "json"
        assert app.conf.accept_content == ["json"]
        assert app.conf.worker_prefetch_multiplier == 1
        assert app.conf.broker_transport_options["visibility_timeout"] == 3600
        assert app.conf.task_default_routing_key == "reviews"


@pytest.mark.asyncio
@pytest.mark.parametrize("queue", ["", "reviews,coding", "bad queue", "reviews\n"])
async def test_invalid_queue_never_publishes(
    settings: QueueSettings, queue: str
) -> None:
    with patch("common.queue.backends.celery._publish") as publish:
        with pytest.raises(ValueError):
            await CeleryQueueProducer(settings).enqueue("review", {}, queue=queue)
    publish.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_payload_never_publishes(settings: QueueSettings) -> None:
    with patch("common.queue.backends.celery._publish") as publish:
        with pytest.raises(ValidationError):
            await CeleryQueueProducer(settings).enqueue(
                "review", {"invalid": object()}, queue="reviews"
            )
    publish.assert_not_called()


@pytest.mark.asyncio
async def test_publication_failure_reaches_caller(settings: QueueSettings) -> None:
    with patch(
        "common.queue.backends.celery._publish",
        side_effect=ConnectionError("broker down"),
    ):
        with pytest.raises(ConnectionError, match="broker down"):
            await CeleryQueueProducer(settings).enqueue("review", {}, queue="reviews")


@pytest.mark.asyncio
async def test_published_task_matches_wire_contract(settings: QueueSettings) -> None:
    app = MagicMock()
    app.__enter__.return_value = app
    with patch("common.queue.backends.celery._create_app", return_value=app):
        job_id = await CeleryQueueProducer(settings).enqueue(
            "review", {"key": [1, True, None]}, queue="reviews"
        )
    wire = app.send_task.call_args.kwargs
    envelope = JobEnvelope.model_validate(wire["args"][0])
    assert envelope.job_id == job_id == wire["task_id"]
    assert envelope.payload == {"key": [1, True, None]}
    assert wire["queue"] == wire["routing_key"] == wire["exchange"] == "reviews"

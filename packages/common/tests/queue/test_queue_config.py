import pytest
from common.config import BaseAppSettings
from common.queue.config import QueueSettings
from pydantic import ValidationError

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "values",
    [
        {"max_attempts": 0},
        {"max_attempts": True},
        {"backoff_base": -1},
        {"backoff_base": float("inf")},
        {"broker_url": "not-a-url"},
        {"queues": {"": "review-engine"}},
        {"queues": {"review": "same", "coding": "same"}},
        {"queues": {"coding": "coding-agent.dead-letter"}},
        {"queues": {}},
        {"queues": {"review": "reviews", "coding": "reviews"}},
        {"job_routes": {}},
        {"job_routes": {"review": "missing"}},
    ],
)
def test_invalid_queue_settings(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        QueueSettings.model_validate(
            {"broker_url": "redis://localhost:6379/0", **values}
        )


def test_settings_load_through_common_config(monkeypatch: pytest.MonkeyPatch) -> None:
    class ServiceSettings(BaseAppSettings):
        queue: QueueSettings

    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv(
        "QUEUE",
        '{"broker_url":"redis://localhost:6379/1","max_attempts":5,'
        '"backoff_base":0.5,'
        '"queues":{"review":"reviews","coding":"coding"},'
        '"job_routes":{"review":"review","coding":"coding"}}',
    )
    settings = ServiceSettings()
    assert settings.queue.max_attempts == 5
    assert settings.queue.backoff_base == 0.5
    assert settings.queue.queue_for_job_type("review") == "reviews"
    assert settings.queue.queue_for_job_type("coding") == "coding"


def test_extensible_routes_support_new_job_types() -> None:
    settings = QueueSettings.model_validate(
        {
            "broker_url": "redis://localhost:6379/0",
            "queues": {
                "review": "reviews",
                "coding": "coding",
                "indexing": "indexing",
            },
            "job_routes": {
                "review": "review",
                "coding": "coding",
                "index_repo": "indexing",
            },
        }
    )
    assert settings.queue_for_job_type("index_repo") == "indexing"
    assert settings.queue_for_logical_name("indexing") == "indexing"


def test_non_redis_broker_urls_are_allowed() -> None:
    settings = QueueSettings.model_validate(
        {
            "broker_url": "amqp://guest:guest@localhost:5672//",
        }
    )
    assert settings.broker_url.startswith("amqp://")


def test_queue_lookup_raises_for_unknown_route() -> None:
    settings = QueueSettings(broker_url="redis://localhost:6379/0")
    with pytest.raises(KeyError):
        settings.queue_for_job_type("unknown")


def test_retry_delays_are_exponential_and_capped() -> None:
    settings = QueueSettings(
        broker_url="redis://localhost:6379/0", backoff_base=2, backoff_max=5
    )
    assert [settings.retry_delay(attempt) for attempt in range(1, 5)] == [2, 4, 5, 5]
    with pytest.raises(ValueError):
        settings.retry_delay(0)

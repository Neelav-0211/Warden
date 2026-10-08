import re
from typing import Self

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    model_validator,
)


def validate_queue_name(queue: str) -> str:
    """Require an unambiguous single queue/routing key."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", queue):
        raise ValueError("Queue names must contain only letters, digits, _, . or -")
    return queue


class QueueSettings(BaseModel):
    """Embed in BaseAppSettings to load from the common environment/YAML sources.

    max_attempts includes the initial delivery. Retry delays are
    backoff_base * 2 ** (attempt - 1), capped at backoff_max seconds.
    visibility_timeout must exceed the longest handler runtime and retry delay.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    broker_url: str
    max_attempts: int = Field(default=3, ge=1, strict=True)
    backoff_base: float = Field(default=1.0, ge=0)
    backoff_max: float = Field(default=300.0, gt=0)
    visibility_timeout: int = Field(default=3600, gt=0)
    queues: dict[str, str] = Field(
        default_factory=lambda: {
            "review": "review-engine",
            "coding": "coding-agent",
        }
    )
    job_routes: dict[str, str] = Field(
        default_factory=lambda: {
            "review": "review",
            "coding": "coding",
        }
    )

    @model_validator(mode="after")
    def validate_settings(self) -> Self:
        TypeAdapter(AnyUrl).validate_python(self.broker_url)

        if not self.queues:
            raise ValueError("At least one queue must be configured")

        for logical_name, queue in self.queues.items():
            validate_queue_name(logical_name)
            validate_queue_name(queue)
            if queue.endswith(".dead-letter"):
                raise ValueError("Service queues cannot use the dead-letter suffix")

        queue_values = list(self.queues.values())
        if len(set(queue_values)) != len(queue_values):
            raise ValueError("Queue names must be distinct")

        if not self.job_routes:
            raise ValueError("At least one job route must be configured")

        for job_type, logical_name in self.job_routes.items():
            validate_queue_name(job_type)
            validate_queue_name(logical_name)
            if logical_name not in self.queues:
                raise ValueError(
                    f"Job route {job_type!r} references unknown queue {logical_name!r}"
                )

        if self.backoff_max >= self.visibility_timeout:
            raise ValueError("visibility_timeout must exceed backoff_max")
        return self

    @property
    def default_queue(self) -> str:
        first_key = next(iter(self.queues))
        return self.queues[first_key]

    def queue_for_job_type(self, job_type: str) -> str:
        logical_name = self.job_routes.get(job_type)
        if logical_name is None:
            raise KeyError(f"No route configured for job type {job_type!r}")
        return self.queues[logical_name]

    def queue_for_logical_name(self, logical_name: str) -> str:
        queue = self.queues.get(logical_name)
        if queue is None:
            raise KeyError(f"Unknown queue {logical_name!r}")
        return queue

    def retry_delay(self, attempt: int) -> float:
        """Return the delay after a failed one-based attempt."""
        if attempt < 1:
            raise ValueError("attempt must be at least one")
        delay = self.backoff_base
        for _ in range(attempt - 1):
            delay = min(delay * 2, self.backoff_max)
            if delay == self.backoff_max or delay == 0:
                break
        return min(delay, self.backoff_max)

# Common Package

Shared code is organized by capability. Backend-specific queue code is kept
separate from the portable contracts and wire schema.

```text
src/common/
    config.py                 Shared environment, dotenv, and YAML settings
    errors.py                 Stable application errors
    types.py                  Shared domain enums
    logging.py                Structured logging
    telemetry.py              Tracing
    db/                       Database models and session management
    queue/
        interface.py          Producer/consumer protocols and handler type
        envelope.py           Backend-independent JSON wire schema
        config.py             Queue names, Redis settings, and retry policy
        backends/
            celery.py         Celery producer and async consumer adapter
        celery_impl.py        Spec 04 compatibility re-exports
tests/
    db/                       Database unit and integration tests
    queue/
        contract_test_queue.py  Backend-independent behavior suite
        conftest.py             Backend factories and Redis testcontainer
        test_*.py               Schema, settings, adapter, and retry tests
    test_*.py                 Shared utility unit tests
```

## Queue Usage

Embed `QueueSettings` in a service's `BaseAppSettings` to use the shared
configuration sources. Infrastructure code constructs the adapter; business
logic accepts `QueueProducer` or `QueueConsumer`.

```python
import asyncio

from common.config import BaseAppSettings
from common.queue import JobEnvelope, QueueConsumer, QueueProducer, QueueSettings
from common.queue.backends.celery import CeleryQueueConsumer, CeleryQueueProducer


class ServiceSettings(BaseAppSettings):
    queue: QueueSettings


async def handle_review(envelope: JobEnvelope) -> None:
    await review_service.process(envelope.job_id, envelope.payload)


async def main() -> None:
    settings = ServiceSettings()
    producer: QueueProducer = CeleryQueueProducer(settings.queue)
    consumer: QueueConsumer = CeleryQueueConsumer(settings.queue)
  review_queue = settings.queue.queue_for_job_type("review")
    await producer.enqueue(
    "review", {"repository": "owner/repo"}, queue=review_queue
    )
  await consumer.consume(review_queue, handle_review)


asyncio.run(main())
```

`review_service` above represents the service's own idempotent job handler.
Both legacy imports from `common.queue.celery_impl` and the explicit backend
imports shown above are supported.

For this settings model, an environment configuration is:

```console
export ENVIRONMENT=local
export QUEUE='{"broker_url":"redis://localhost:6379/0","max_attempts":3,"backoff_base":1,"queues":{"review":"review-engine","coding":"coding-agent"},"job_routes":{"review":"review","coding":"coding"}}'
```

The same `queue` object can be supplied through the shared YAML settings
source. Queue names allow letters, digits, underscores, periods, and hyphens.
Configured review and coding queue names must differ and cannot end in
`.dead-letter`. Consumers on distinct names are isolated; consumers on the
same name compete for work.

## Delivery And Retries

- Delivery is **at least once**, not exactly once. Make handlers idempotent,
  using `job_id` to deduplicate side effects. A publish whose outcome is unknown
  can also leave a delivered job even when the caller receives an error.
- An envelope contains `job_id`, `job_type`, a JSON-object `payload`, an aware
  `enqueued_at` timestamp, and a one-based `attempt` (default `1`). Retries keep
  the ID, payload, and enqueue timestamp.
- `max_attempts` includes the initial delivery. The delay after failed attempt
  `n` is `min(backoff_base * 2 ** (n - 1), backoff_max)` seconds. Defaults are
  three attempts, a one-second base, and a 300-second cap. A zero base permits
  immediate retries.
- At exhaustion, the final envelope is published to `<queue>.dead-letter`
  before the original is acknowledged. Consume that queue through the same
  interface to inspect or archive failed jobs. A successful dead-letter handler
  acknowledges the record. There is no automatic replay to the original queue.
- A failed retry or dead-letter publication leaves the original job available
  for redelivery. Broker redelivery can repeat an attempt, so the configured
  limit bounds logical retry attempts, not invocations after crashes or outages.
- `consume()` runs until cancelled. Each call owns a solo worker thread and
  awaits handlers on the caller's event loop. Cancellation cancels the active
  handler, rejects unfinished work for redelivery, and joins the worker. Handlers
  must cooperate with cancellation and avoid blocking the event loop.
- `visibility_timeout` defaults to 3600 seconds and must exceed both the longest
  handler runtime and maximum retry delay. Crash recovery may take this long.
  Use competing consumers or service replicas to increase throughput.
- Redis durability and availability depend on deployment persistence settings;
  the adapter cannot protect jobs against loss of the broker's data.

## Tests

From the repository root:

```console
uv run --package warden-common pytest packages/common/tests -m unit
uv run --package warden-common pytest packages/common/tests/queue -m integration
uv run --package warden-common pytest packages/common/tests/db -m integration
```

Integration tests start real Redis or PostgreSQL through testcontainers and
require Docker. Unit tests do not connect to external services. A new backend
must supply the producer/consumer fixture and inherit the same `QueueContract`
suite; the contract tests do not import Celery.
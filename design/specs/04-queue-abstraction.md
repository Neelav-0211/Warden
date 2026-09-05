# Spec 04: Queue Abstraction

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 02
- **Owns**: `packages/common/queue/`

## Goal

A pluggable task-queue interface so `api-gateway` can enqueue work and
`review-engine`/`coding-agent` can consume it, without either side
hardcoding Celery/Redis specifics into business logic.

## Scope

- `QueueProducer` / `QueueConsumer` interface (`Protocol`), independent of
  broker choice.
- Default implementation: Celery + Redis, matching the tech-stack
  decision. `arq` noted as swappable — the contract test suite (see
  below) is what makes that swap safe later, not implemented in this
  spec unless time allows.
- Job envelope schema (Pydantic): `JobEnvelope { job_id, job_type,
  payload: dict, enqueued_at, attempt }` — this is the on-wire shape
  every producer/consumer agrees on, independent of Celery's own
  metadata.
- Per-service consumer group configuration (review-engine and
  coding-agent must be able to consume from independently named
  queues/routing keys without cross-talk).
- Retry/backoff policy as explicit config (max attempts, backoff base),
  not a Celery default left implicit.

## Public Interface

```python
# common/queue/interface.py
class QueueProducer(Protocol):
    async def enqueue(self, job_type: str, payload: dict, *, queue: str) -> str: ...

class QueueConsumer(Protocol):
    async def consume(self, queue: str, handler: Callable[[JobEnvelope], Awaitable[None]]) -> None: ...

# common/queue/celery_impl.py
class CeleryQueueProducer(QueueProducer): ...
class CeleryQueueConsumer(QueueConsumer): ...
```

## TDD Plan

1. `test_job_envelope.py` (unit): schema validation, round-trip
   serialize/deserialize.
2. `contract_test_queue.py` (shared, parametrized fixture): a suite of
   behavioral tests — enqueue then consume delivers the same payload;
   a handler raising an exception triggers a retry up to max attempts
   then lands in a dead-letter state; two different `queue` names never
   cross-deliver. Written against the `QueueProducer`/`QueueConsumer`
   interfaces only, not the Celery implementation, so any future backend
   runs the same suite (per repo-wide rule in spec 00).
3. `test_celery_impl_integration.py`: instantiate the contract suite
   against `CeleryQueueProducer`/`Consumer` backed by a real Redis
   (testcontainers), using an in-process fake handler.
4. `test_retry_policy_integration.py`: simulate a handler that fails N
   times then succeeds; assert it's retried exactly per configured
   policy and not beyond it.

## Acceptance Criteria

- [ ] `QueueProducer`/`QueueConsumer` `Protocol`s defined and documented
      with docstrings covering delivery semantics (at-least-once).
- [ ] Contract test suite passes against the Celery/Redis implementation.
- [ ] Retry policy is configuration-driven (max attempts, backoff),
      verified by test that a handler failing exactly `max_attempts`
      times is not retried again.
- [ ] Two services consuming different `queue` names never receive each
      other's jobs, verified by integration test with both queues active
      simultaneously.
- [ ] `JobEnvelope` round-trips through serialize/deserialize with no
      data loss, verified by property-based or example-based test.

# Spec 11: API Gateway

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 02, 04, 08
- **Owns**: `services/api-gateway/`

## Goal

Single ingress point: verifies inbound GitHub webhooks, authenticates
direct API/CLI task submissions, and enqueues jobs for `review-engine`
and `coding-agent` — contains no business logic of its own.

## Scope

- **FastAPI app** with routes:
  - `POST /webhooks/github` — verifies signature (spec 08's
    `verify_signature`), parses event type, enqueues a `review` job for
    PR/comment events via `common.queue` (spec 04) with the `review-
    engine`'s queue name.
  - `POST /tasks` — direct task submission (issue text/repo/ref), auth'd
    via API key/token, enqueues a `coding-agent` job.
  - `GET /tasks/{task_id}` — reads current status from `Task`/`TaskStep`
    (spec 03) for polling clients.
  - `GET /healthz` — liveness/readiness, checks DB + queue connectivity.
- **Auth**: API-key based for `/tasks*` endpoints (simplest viable for
  self-host v1); webhook route relies solely on GitHub's HMAC signature,
  not API keys.
- **Rate limiting**: per-IP/per-key basic rate limit on `/tasks` (e.g.
  token bucket) to protect a self-hosted instance from accidental abuse.
- Request/response schemas as Pydantic models; OpenAPI docs enabled
  (FastAPI default) since this is the one HTTP-facing surface.

## Non-Goals

- No review/agent logic here — this service only validates and enqueues.
  Any behavior that looks like "decide what the review should say"
  belongs in `review-engine` (spec 12).

## Public Interface (HTTP contract)

```
POST /webhooks/github        (GitHub signature header required)
POST /tasks                  (X-API-Key header required) -> {task_id}
GET  /tasks/{task_id}        -> {status, steps_summary}
GET  /healthz                -> {ok: bool, db: bool, queue: bool}
```

## TDD Plan

1. `test_webhook_signature.py` (unit, FastAPI `TestClient`): valid
   signature + supported event type → 202 + job enqueued (assert via a
   fake `QueueProducer`); invalid signature → 401, nothing enqueued;
   unsupported event type → 200/ignored, nothing enqueued (don't error on
   events we don't care about).
2. `test_task_submission.py` (unit): valid API key + valid payload → 201
   + `Task` row created (real DB or a repository fake) + job enqueued
   with matching `task_id`; missing/invalid API key → 401; malformed
   payload → 422 with field-level errors (Pydantic default).
3. `test_task_status.py` (unit): existing task id → 200 with correct
   status derived from persisted `TaskStep`s; unknown id → 404.
4. `test_rate_limit.py` (unit): N+1th request within the window from the
   same key → 429; verified with a fake clock, no real waiting.
5. `test_healthz_integration.py`: `/healthz` reflects real DB/queue
   outages (simulate by pointing at an unreachable DB) → `ok: false`
   with per-dependency detail, not a blanket 500.

## Acceptance Criteria

- [ ] Webhook route rejects invalid/tampered signatures with 401,
      verified by test; never enqueues a job in that case.
- [ ] Task submission requires a valid API key, verified by test; issues
      a `task_id` immediately and enqueues the corresponding job.
- [ ] `/tasks/{id}` accurately reflects persisted task status, verified
      by test against real DB state.
- [ ] Rate limiting enforced and verified by test with a fake clock.
- [ ] `/healthz` distinguishes DB vs. queue failures in its response
      body, verified by test.
- [ ] No review/agent decision logic exists in this service — enforced
      by code review checklist referencing this spec (no calls to
      `ModelProvider` from `api-gateway`).

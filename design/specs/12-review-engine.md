# Spec 12: Review Engine Service

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 04, 05, 06, 07, 08, 11
- **Owns**: `services/review-engine/`

## Goal

The stateless worker that consumes review jobs enqueued by `api-gateway`,
builds context, generates review comments via the Model Gateway, and
posts them back to GitHub. No persistent workspace, no long-lived state
beyond a `ReviewRecord` row.

## Scope

- `QueueConsumer` (spec 04) handler for the `review` job type.
- Context building: fetch diff + changed files via `github-integration`
  (spec 08); query `DatasourceConnector` (spec 07) for relevant domain
  chunks; assemble a bounded prompt (respecting the selected model's
  `max_context_tokens` from spec 05's `Capabilities`).
- Review generation: call `ModelGatewayRouter` (spec 05) with a
  structured request expecting a `ReviewResult` (Pydantic: overall
  summary + list of inline comments with file/line/body).
- Posting results: `github-integration.post_review_comment` for inline +
  summary comments.
- Persistence: write a `ReviewRecord` (spec 03) with status transitions
  (`received → processing → posted` or `failed`), including error detail
  on failure so retries/observability have something to show.
- Idempotency: re-processing the same PR event (e.g. due to at-least-
  once queue delivery) must not double-post duplicate comments — dedupe
  by PR + commit SHA + a content hash, or by checking existing bot
  comments before posting.

## Non-Goals

- No workspace provisioning, no code execution — review-engine only
  reasons over diffs/retrieved text (per the architecture doc's "no
  persistent workspace" property).

## TDD Plan

1. `test_context_builder.py` (unit, fake GitHub client + fake
   connector): assembled prompt includes diff content and top-k
   retrieved chunks, and is truncated to fit `max_context_tokens`.
2. `test_review_generation.py` (unit, `FakeModelProvider`): scripted
   model response parses into a valid `ReviewResult`; malformed model
   output (fails schema) is retried once with a repair prompt, then
   surfaces a typed error if still invalid.
3. `test_posting.py` (unit, fake GitHub client): `ReviewResult` maps to
   the correct sequence of `post_review_comment` calls (inline + one
   summary).
4. `test_idempotency.py` (unit): processing the same job envelope twice
   results in exactly one set of posted comments, verified via a fake
   GitHub client call-count assertion.
5. `test_review_record_lifecycle_integration.py` (integration, real DB):
   status transitions land correctly for both success and failure paths,
   including error detail on failure.
6. `test_end_to_end_worker_integration.py` (integration): a job placed on
   the real queue (spec 04's Celery/Redis) is picked up by the worker
   entrypoint and results in a `ReviewRecord` with status `posted`,
   using `FakeModelProvider` + fake GitHub client + real queue + real DB.

## Acceptance Criteria

- [ ] A review job produces a bounded, correctly-truncated prompt
      including both diff and retrieved domain context, verified by
      test.
- [ ] Malformed model output triggers exactly one repair retry before
      failing loudly (typed error), verified by test.
- [ ] Duplicate delivery of the same review job never results in
      duplicate posted comments, verified by test.
- [ ] `ReviewRecord` status accurately reflects success/failure,
      including error detail on failure, verified against real DB.
- [ ] End-to-end integration test (real queue + real DB, faked model/
      GitHub) passes, proving the worker wiring itself (not just the
      logic units) works.
- [ ] Service holds no state between jobs beyond what's persisted to
      Postgres — verified by a restart-mid-batch integration test
      (kill and restart the worker process between two queued jobs;
      both still complete correctly).

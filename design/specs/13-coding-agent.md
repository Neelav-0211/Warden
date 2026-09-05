# Spec 13: Coding Agent Service

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 03, 04, 08, 10
- **Owns**: `services/coding-agent/`

## Goal

The async worker that consumes task jobs, drives an `AgentSession`
(spec 10) to completion, and is resilient to crashes mid-task via
persisted state.

## Scope

- `QueueConsumer` (spec 04) handler for the `coding-agent` job type:
  looks up (or creates) the `Task` row, constructs an `AgentSession`
  (fresh via `run()` or resumed via `resume()` depending on whether
  `TaskStep`s already exist for this task), and drives it to completion.
- Crash recovery: on worker startup, scan for `Task`s in an in-progress
  status with no active consumer claim, and re-enqueue/resume them
  (concretely define the claim mechanism — e.g. a `claimed_by`/
  `claimed_at` column with a staleness timeout — to avoid two workers
  double-running the same task).
- Wires concrete dependencies into `AgentSession`: real `ModelProvider`
  (via Model Gateway router, spec 05/06), real `DatasourceConnector`
  (spec 07), real `WorkspaceDriver` (spec 09), real `GitHubClient`
  (spec 08).
- Reports terminal task status back (success/failure/budget-exhausted)
  in a form `api-gateway`'s `GET /tasks/{id}` (spec 11) can surface.

## Non-Goals

- No agent-loop logic itself (owned by spec 10) — this service is purely
  the queue-consumption + dependency-wiring + crash-recovery shell around
  `AgentSession`.

## TDD Plan

1. `test_job_handler.py` (unit, fake `AgentSession`/dependencies): a
   fresh task job constructs a new session and calls `run()`; a job for a
   task with existing `TaskStep`s calls `resume()` instead — verified by
   spy/fake assertions, not real agent execution (keeps this fast/unit).
2. `test_claim_mechanism.py` (integration, real DB): two worker instances
   racing to claim the same task — exactly one succeeds in claiming it,
   verified via a concurrency test (e.g. `asyncio.gather` on both claim
   attempts).
3. `test_stale_claim_recovery_integration.py`: a task claimed by a
   "dead" worker (claimed_at older than the staleness timeout, no
   progress) is reclaimed and resumed by a new worker on startup scan.
4. `test_status_reporting_integration.py`: after a scripted `AgentSession`
   run (success and failure variants) completes, the task's persisted
   status matches what `api-gateway`'s status endpoint contract expects.
5. `test_full_worker_integration.py`: end-to-end — job on real queue
   (spec 04) → worker picks it up → drives a real `AgentSession` (spec
   10) using `FakeModelProvider` + real `LocalDockerDriver` (spec 09) +
   real DB → task ends `Done` with a recorded result.

## Acceptance Criteria

- [ ] Fresh vs. resumed session construction is correctly chosen based on
      persisted state, verified by test.
- [ ] Exactly one worker ever actively runs a given task at a time,
      verified by a concurrent-claim test.
- [ ] A task whose worker died mid-run is correctly reclaimed and resumed
      by another worker after the staleness timeout, verified by test.
- [ ] Terminal task status (success/failure/budget-exhausted) is
      persisted in the shape `api-gateway` expects, verified by test.
- [ ] End-to-end integration test (real queue + real DB + real Docker
      driver, faked model) passes.

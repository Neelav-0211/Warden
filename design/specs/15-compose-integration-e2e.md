# Spec 15: Compose Integration / End-to-End

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 12, 13, 14, 16
- **Owns**: `/infra/compose/docker-compose.yml` (+ overrides)

## Goal

Prove the whole Phase 1 system works together via a single `docker
compose up`, exercising the two headline flows described in the
architecture doc: webhook → review comment, and task → agent → PR.

## Scope

- Compose file bringing up: Postgres (+pgvector), Redis, `api-gateway`,
  `review-engine`, `coding-agent`, `workspace-provisioner` (as used by
  coding-agent), plus the spec 14 observability profile as optional.
- Environment wiring via `.env` (extending spec 01's `.env.example`) for
  all required secrets/config (GitHub App credentials, model provider
  keys, etc.) — operator fills these in; sane local defaults for
  everything else (DB/queue URLs point at the Compose service names).
- A documented "smoke test" script (`scripts/smoke_test.sh` or a pytest
  integration test) that:
  1. Brings the stack up.
  2. Sends a synthetic signed webhook payload to `api-gateway` and polls
     for a `ReviewRecord` reaching `posted` (against a test/fake GitHub
     target, or a real disposable repo — decide and document).
  3. Submits a synthetic task via `POST /tasks` and polls
     `GET /tasks/{id}` until it reaches a terminal state.
  4. Tears the stack down.

## Non-Goals

- No production deployment manifests (Helm/K8s) — Compose is the OSS
  distribution mechanism per the tech-stack doc; production/managed
  deployment is out of scope for this repo's specs.

## TDD Plan

Since this spec is about wiring rather than new logic, its "tests" are
the smoke test itself, developed iteratively:

1. Write the smoke test script against the *expected* Compose topology
   first (it will fail until the Compose file exists) — this pins down
   exactly what the Compose file must expose (ports, health endpoints).
2. Bring up services one at a time in the Compose file, re-running the
   smoke test's individual assertions (health checks first, then the
   webhook flow, then the task flow) until each passes.
3. Add a chaos check: kill the `coding-agent` container mid-task, restart
   it, assert the smoke test's task-flow assertion still eventually
   reaches a terminal state (proving spec 13's crash recovery works at
   the Compose level, not just in isolated integration tests).

## Acceptance Criteria

- [ ] `docker compose up` (core profile, no observability) brings up all
      Phase 1 services healthy (`/healthz` green on `api-gateway`, DB/
      queue reachable).
- [ ] Smoke test's webhook flow assertion passes: signed webhook →
      `ReviewRecord` reaches `posted`.
- [ ] Smoke test's task flow assertion passes: `POST /tasks` → task
      reaches a terminal state, with a PR reference recorded (real or
      fake GitHub target, as documented).
- [ ] Chaos check passes: killing and restarting `coding-agent` mid-task
      still results in the task reaching a terminal state.
- [ ] `docker compose --profile observability up` additionally brings up
      Prometheus/Grafana/Loki healthy, per spec 14.
- [ ] The smoke test is runnable in CI (spec 16) as the final pipeline
      stage before image publish.

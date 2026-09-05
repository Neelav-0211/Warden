# Spec 16: CI/CD

- **Status**: Not Started
- **Phase**: 1 (extended in Phase 2 by spec 17)
- **Depends on**: 01
- **Owns**: `.github/workflows/`

## Goal

Automate lint → type-check → test → build → publish for every push/PR,
using the tooling commands spec 01 already proved work locally.

## Scope

- **PR pipeline** (`.github/workflows/ci.yml`): on every PR —
  1. `ruff check` + `ruff format --check`.
  2. `mypy --strict`.
  3. `pytest -m unit` (fast, no external services).
  4. `pytest -m integration` (spins up Postgres/Redis service containers
     in the Actions job, or uses `testcontainers` directly).
  5. Build each service's Docker image (no push) to catch Dockerfile
     breakage early.
- **Release pipeline** (`.github/workflows/release.yml`): on tag push —
  builds and pushes each service's image to GHCR, tagged with the git
  tag + `latest`.
- Job matrix/parallelization: unit tests, integration tests, and image
  builds run as independent parallel jobs, not one long serial job.
- Branch protection recommendation documented (require CI green before
  merge) — recorded here since it's a repo setting, not code.

## Non-Goals

- No Go pipeline yet (added by spec 17 once the Go service exists).
- No deployment automation beyond image publish (operators self-host;
  this repo doesn't manage their infra).

## TDD Plan

CI/CD has no application-level unit tests; validation is done by
observing pipeline behavior on deliberately crafted branches:

1. Push a branch with a lint violation → confirm the lint job fails and
   the others still run/report independently (parallel jobs, not
   blocked by lint failing).
2. Push a branch with a type error → confirm the type-check job fails.
3. Push a branch with a failing unit test → confirm the test job fails
   and reports which test.
4. Push a branch with a broken Dockerfile for one service → confirm only
   that service's build job fails, others succeed.
5. Push a tag → confirm images land in GHCR with both the tag and
   `latest`.

## Acceptance Criteria

- [ ] PR pipeline runs lint, type-check, unit tests, integration tests,
      and Docker builds as independent parallel jobs.
- [ ] A failure in any one job is clearly attributed (job name +
      failing step) without other jobs being blocked from running.
- [ ] Integration test job successfully provisions Postgres/Redis inside
      the CI environment (service containers or testcontainers) with no
      manual setup.
- [ ] Tag push triggers image build + push to GHCR for every service,
      tagged correctly, verified by inspecting GHCR after a real tag
      push.
- [ ] Total PR pipeline wall-clock time is documented here once measured,
      as a baseline to catch future regressions.

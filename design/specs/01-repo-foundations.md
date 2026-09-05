# Spec 01: Repository Foundations

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: none
- **Owns**: repo root, `/services/*` (empty scaffolds), `/packages/*` (empty
  scaffolds), `/infra`, tooling config files

## Goal

Stand up the monorepo skeleton and developer tooling so every subsequent
spec can `cd` into a package/service that already has working lint,
type-check, and test commands — with nothing to implement yet.

## Scope

- Monorepo layout matching the architecture doc:
  ```
  /services/{review-engine,coding-agent,workspace-provisioner,model-gateway,api-gateway}
  /packages/{agent-core,github-integration,datasource-connectors,common}
  /infra/{docker,compose}
  ```
- Python workspace tooling: `uv` (or `poetry` — pick one, record the
  decision) for dependency management, with a root workspace config and
  one `pyproject.toml` per package/service.
- `ruff` config (lint + format) at repo root, inherited by all packages.
- `mypy` strict config at repo root, inherited by all packages.
- `pytest` config: root `pytest.ini`/`pyproject` section defining markers
  `unit` (default, no external deps) and `integration` (requires Docker/DB/
  network — excluded from default run).
- `pre-commit` config running ruff + mypy on changed files.
- Empty `Dockerfile` per service (placeholder `FROM python:3.12-slim`,
  filled in by each service's own spec).
- Root `README.md` stub linking to `/design`.
- `.env.example` documenting expected environment variables (empty at this
  stage, appended to by later specs).

## Non-Goals

- No actual business logic, no Compose file wiring services together
  (that's spec 15), no CI pipeline yet (that's spec 16, though it depends
  on this spec's tooling commands existing).

## TDD Plan

This spec is tooling-only, so "tests" are the tooling commands themselves
proving they work against a trivial fixture:

1. Write a throwaway `packages/common/tests/test_scaffold.py` with a single
   `def test_true(): assert True`.
2. Confirm `pytest -m unit` from repo root discovers and runs it.
3. Add a deliberately badly-formatted/badly-typed throwaway file, confirm
   `ruff check` and `mypy` both fail on it, then fix it and confirm both
   pass — proving the configs are actually wired, not just present.
4. Remove the throwaway fixtures once tooling is proven (keep only real
   package structure).

## Acceptance Criteria

- [ ] Directory structure matches the architecture doc exactly (`/services`,
      `/packages`, `/infra`).
- [ ] `pytest -m unit` runs successfully from repo root with zero tests
      (after throwaway fixtures are removed) and zero configuration errors.
- [ ] `ruff check .` and `ruff format --check .` both pass on a clean
      checkout.
- [ ] `mypy .` (strict) passes on a clean checkout (nothing to type-check
      yet, but config must be valid and runnable).
- [ ] `pre-commit run --all-files` passes.
- [ ] Each service/package directory has its own `pyproject.toml` that
      resolves via the root workspace tool without dependency conflicts.
- [ ] Each service has a placeholder `Dockerfile` that builds successfully
      (`docker build` exits 0) even though it runs nothing meaningful yet.
- [ ] `.env.example` exists and is referenced from the root `README.md`.

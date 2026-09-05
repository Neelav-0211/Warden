# Spec 03: Database Layer

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 02
- **Owns**: `packages/common/db/` (engine/session, base models), Alembic
  migrations directory at repo root (`/infra/migrations` or per-package —
  pick one location and document it here once decided)

## Goal

A single async SQLAlchemy 2.0 layer, shared by every service that needs
persistence (`coding-agent` task state, `review-engine` review records),
with Alembic-managed migrations and the `pgvector` extension available
for spec 07.

## Scope

- Async engine/session factory: `common.db.get_engine(settings)`,
  `common.db.session_scope()` async context manager.
- Base ORM models:
  - `Task` — id, status (`TaskStatus`), repo, ref, created_at, updated_at.
  - `TaskStep` — id, task_id (FK), step_index, kind (plan/tool_call/
    observation), payload (JSONB), created_at. This is the "tool-call
    history" the architecture doc requires for crash-resumable agent
    state.
  - `ReviewRecord` — id, pr_number, repo, status (`JobStatus`), summary,
    created_at.
  - `Job` — generic queue-job bookkeeping row (id, queue_name, status,
    attempts, last_error) used by both subsystems' workers for
    observability independent of the broker's own state.
- Alembic setup: env.py wired to the async engine, one initial migration
  creating the above tables plus `CREATE EXTENSION IF NOT EXISTS vector`.
- A `testcontainers`-backed pytest fixture (`pg_container`) that spins up
  real Postgres 16 with `pgvector` for integration tests, shared by any
  later spec that needs a real DB.

## Non-Goals

- No repository/query methods beyond basic CRUD needed to prove the
  schema (rich query methods belong to the specs that need them, e.g.
  spec 10 owns `TaskStepRepository.append_step`).

## Public Interface

```python
# common/db/session.py
def get_engine(settings: DbSettings) -> AsyncEngine: ...
@asynccontextmanager
async def session_scope(engine: AsyncEngine) -> AsyncIterator[AsyncSession]: ...

# common/db/models.py
class Task(Base): ...
class TaskStep(Base): ...
class ReviewRecord(Base): ...
class Job(Base): ...
```

## TDD Plan

1. `test_models_unit.py` (unit, no DB): assert model classes declare the
   expected columns/types via SQLAlchemy's `__table__.columns` metadata —
   catches typos without needing a real database.
2. `test_migrations_integration.py` (integration, `pg_container` fixture):
   run `alembic upgrade head` against the ephemeral container, assert all
   expected tables + the `vector` extension exist.
3. `test_crud_integration.py` (integration): insert a `Task`, append two
   `TaskStep` rows referencing it, assert FK cascade behavior on delete,
   assert `updated_at` auto-updates on modification.
4. `test_session_scope_integration.py`: assert `session_scope` commits on
   success and rolls back on an exception raised inside the block.

Write all four test files (failing, against not-yet-existing models)
before writing `models.py`/migration files.

## Acceptance Criteria

- [ ] `alembic upgrade head` succeeds against a fresh Postgres 16 +
      pgvector instance, verified in CI via `pg_container` fixture.
- [ ] `alembic downgrade base` succeeds cleanly (round-trip verified).
- [ ] All four ORM models exist with the columns listed above and are
      covered by the unit metadata test.
- [ ] `session_scope` commit/rollback behavior verified by test.
- [ ] Integration tests run in CI via the `integration` pytest marker,
      isolated from the default `unit` run (spec 01's marker scheme).
- [ ] No service imports `sqlalchemy` directly for connection setup —
      all go through `common.db`.

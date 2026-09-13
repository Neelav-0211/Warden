# Spec 02: Common Package (`packages/common`)

- **Status**: Done
- **Phase**: 1
- **Depends on**: 01
- **Owns**: `packages/common/`

## Goal

Provide the shared building blocks every other package/service imports:
configuration loading, structured logging, base error types, and shared
Pydantic types. Nothing provider- or infra-specific lives here.

## Scope

- **Config loader**: `common.config.Settings` (Pydantic v2
  `BaseSettings`) that reads from environment variables plus an optional
  YAML/`.env` file, with per-service subclasses composing a shared base
  (e.g. `LogLevel`, `ENVIRONMENT`, DB URL, Redis URL). Fails fast with a
  clear error listing missing required fields — never silently defaults a
  credential.
- **Structured logging**: `common.logging.get_logger(name)` wrapping
  `structlog`, configured for JSON output in non-local environments and
  pretty console output when `ENVIRONMENT=local`. Every log line must
  support binding a `task_id`/`job_id`/`request_id` context var.
- **Telemetry bootstrap**: `common.telemetry.init_tracing(service_name)`
  wiring OpenTelemetry SDK with an OTLP exporter (configurable endpoint,
  no-op if unset) — just the bootstrap function; actual span
  instrumentation happens in each service's own spec.
- **Base error types**: `common.errors` — `WardenError` base, with
  subclasses like `ConfigError`, `NotFoundError`, `ExternalServiceError`,
  each carrying a stable `code` string for consistent API error bodies.
- **Shared enums/value types**: `common.types` — e.g. `TaskStatus`,
  `JobStatus` enums referenced by both the database layer and services
  (defined once here so `packages` and `services` don't redefine them).

## Non-Goals

- No database models (spec 03), no queue client (spec 04), no HTTP
  server code.

## Public Interface

```python
# common/config.py
class BaseAppSettings(BaseSettings):
    environment: Literal["local", "staging", "production"]
    log_level: str = "INFO"
    otlp_endpoint: str | None = None

# common/logging.py
def get_logger(name: str) -> structlog.BoundLogger: ...
def bind_context(**kwargs: Any) -> None: ...  # e.g. task_id=...

# common/telemetry.py
def init_tracing(service_name: str, settings: BaseAppSettings) -> None: ...

# common/errors.py
class WardenError(Exception):
    code: str
class ConfigError(WardenError): ...
class NotFoundError(WardenError): ...
class ExternalServiceError(WardenError): ...
```

## TDD Plan

1. `test_config.py`: assert `BaseAppSettings` raises `ConfigError` (not a
   raw `pydantic.ValidationError` leaking out) when a required env var is
   missing; assert it correctly loads from environment variables and from
   a temp `.env` file; assert unknown extra env vars don't crash it.
2. `test_logging.py`: assert `get_logger` returns a logger that emits
   valid JSON to stdout when `environment != local`; assert `bind_context`
   values appear in subsequent log records within the same context
   (use `structlog.testing.capture_logs`).
3. `test_telemetry.py`: assert `init_tracing` is a no-op (doesn't raise,
   doesn't require network) when `otlp_endpoint` is `None`; assert it
   configures a tracer provider when an endpoint is set (verify via
   `opentelemetry.trace.get_tracer_provider()` type, no real network
   call needed).
4. `test_errors.py`: assert each error subclass carries the expected
   `.code` and that they're all instances of `WardenError`.
5. `test_types.py`: assert enum members match what spec 03 will persist
   (locks the contract before the DB layer is built).

All tests in this spec run under the `unit` marker — no network, no DB,
no Docker.

## Acceptance Criteria

- [x] `BaseAppSettings` fails fast with `ConfigError` listing every
      missing field, verified by test.
- [x] `get_logger`/`bind_context` produce structured logs with bound
      context fields present, verified by test using
      `structlog.testing.capture_logs`.
- [x] `init_tracing` is safely a no-op with no OTLP endpoint configured,
      verified by test.
- [x] 100% of `common` public functions have type hints and pass `mypy
      --strict`.
- [x] `TaskStatus`/`JobStatus` enums are defined once and imported (not
      redefined) by every later spec that needs them.
- [x] Test coverage on `packages/common` ≥ 90% (unit tests only).

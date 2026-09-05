# OSS Engine — Tech Stack Specification

## Context & Goals

Solo-built, self-hosted project. Stack choices are optimized for two
things simultaneously: (1) fastest path to a working end-to-end system,
and (2) maximum overlap with industry standard tools. Build order is phased so no more than one new
language/ecosystem is introduced at a time.

---

## Phase 1 — Core System (Python-first)

Everything runs as Python services initially, including the local Docker
driver for the Workspace Provisioner. Goal: one working end-to-end loop
(webhook → review comment; task → agent → PR) before adding Go or
TypeScript.

### Language & Runtime
- **Python 3.12+**
- `asyncio` throughout — all services are I/O-bound (API calls, subprocess
  exec, DB/queue access).

### Web / API Framework
- **FastAPI** — for `api-gateway` and any service exposing HTTP.
- **Pydantic v2** — schema validation and structured output parsing.
  Deliberately learned in depth: this is the backbone of tool-calling /
  structured-output patterns used across the agent loop and the model
  gateway, and it is one of the most interview-relevant libraries in this
  space.
- **Uvicorn** (ASGI server).

### Agent Loop / Model Integration
- **Native provider SDKs** (`anthropic`, `openai`, provider-specific for
  Bedrock/Azure) — no LangChain/LangGraph in Phase 1. The tool-use loop,
  retry/backoff, and streaming handling are hand-written in
  `packages/agent-core` to build real understanding of what agent
  frameworks abstract away.
- **LangGraph** introduced only later (optional, Phase 2+) as an
  informed choice, not a starting crutch.
- **httpx** for any raw HTTP calls to model providers not covered by SDKs
  (e.g. generic OpenAI-compatible local endpoints — vLLM, Ollama).

### Task Queue
- **Redis** (broker + result backend).
- **Celery** — default choice; widely referenced in Python job postings,
  worth being fluent in even though heavier than alternatives.
- **`arq`** — noted as an asyncio-native lightweight alternative; can be
  swapped in if Celery's process model becomes a friction point locally.

### Database
- **PostgreSQL 16+**
  - Task/job state, agent step history, review records.
  - **pgvector** extension as the default `DatasourceConnector`
    implementation — zero extra infrastructure for a self-hoster.
- **SQLAlchemy 2.0** (async) + **Alembic** for migrations.

### Datasource Connectors (pluggable)
- Default: pgvector (as above).
- Optional adapters: Pinecone, Weaviate, Qdrant — implemented against the
  same `DatasourceConnector` interface, selected via config.

### GitHub Integration
- **GitHub App** auth flow (JWT → installation access token) implemented
  directly rather than fully hidden behind a library, to actually
  understand the flow.
- **PyGithub** or raw `httpx` calls against the REST/GraphQL API for
  PR/issue/comment operations.
- **Webhook signature verification** via HMAC (`hmac`/`hashlib`,
  standard library — no need for an extra dependency).

### Workspace Provisioner (Phase 1 driver only)
- **Docker SDK for Python** (`docker-py`) driving local Docker containers.
- Exposed via the same internal interface
  (`create/exec/attach/destroy`) that the Go rewrite (Phase 2) will
  implement — defined as a Python `Protocol` / abstract base class now so
  the contract is explicit before porting.
- **Debug attach**: a simple `ttyd` or `websocat`-based web terminal
  bridge into the container, or plain `docker exec` over SSH for a first
  pass.

### Containerization (local self-host)
- **Docker** + **Docker Compose** — one compose file to bring up
  Postgres, Redis, and all Python services locally. This is the primary
  OSS distribution mechanism (`docker compose up`).

### Testing
- **pytest** + **pytest-asyncio**.
- **httpx**'s `AsyncClient` / FastAPI `TestClient` for API tests.
- **testcontainers-python** for integration tests against real
  Postgres/Redis in CI.

### Linting / Formatting / Typing
- **ruff** (lint + format, replaces flake8/black/isort).
- **mypy** (strict mode) — typed code matters more here than in typical
  scripting work, since `agent-core` and `model-gateway` interfaces are
  shared across services.

### CI/CD
- **GitHub Actions**: lint → type-check → test → build Docker images →
  push to GHCR (GitHub Container Registry) on tag.

### Observability
- **OpenTelemetry** (Python SDK) for traces across the agent loop —
  instrumented from day one so "why did the agent do X" is answerable
  from traces, not just logs.
- **structlog** for structured JSON logging.
- Local stack: **Prometheus** + **Grafana** + **Loki**, wired up via the
  Compose file as an optional profile (`docker compose --profile
  observability up`).

---

## Phase 2 — Workspace Provisioner Rewrite (Go)

Once the Provisioner's interface is stable and proven against the Python
local-Docker driver, port the service to Go. This is a natural, scoped
first Go project because you already have a working contract to port
against.

### Language & Runtime
- **Go 1.22+**

### Container / Orchestration Clients
- **Docker SDK for Go** (`docker/docker/client`) — local driver.
- **`client-go`** — Kubernetes driver, used later for the managed
  offering but worth building the abstraction here so both drivers share
  one Go interface.

### Service Interface
- **gRPC** (via `google.golang.org/grpc` + Protocol Buffers) exposing
  `Create`, `Exec`, `Attach` (streaming), `Destroy` — gRPC's streaming
  support maps naturally onto `attach()`'s live terminal/exec use case.
- Alternative if you want to stay simpler: plain REST + WebSocket for the
  `attach` stream. gRPC is the more industry-standard choice for
  service-to-service infra APIs and worth the extra learning curve.

### Testing
- Standard library `testing` + `testify` for assertions.
- `dockertest` for integration tests against a real Docker daemon.

### CI/CD
- Extend the same GitHub Actions pipeline: add a Go build/test/lint job
  (`golangci-lint`), produce a separate container image for this service.

---

## Phase 3 — (Optional, OSS-side) Dashboard / Local UI

Not required for OSS (which is primarily API + webhook driven), but if a
local web UI is added for reviewing agent runs or browsing workspace
sessions:

- **TypeScript + Next.js + React + TailwindCSS**
- Talks to `api-gateway` over REST — no shared runtime with the Python
  services.

This is intentionally the same stack as the managed offering's dashboard
(see companion doc), so any UI work here transfers directly.

---

## Summary Table

| Concern | Choice |
|---|---|
| Core services language | Python 3.12+ (FastAPI, Pydantic, asyncio) |
| Agent loop | Hand-written, native provider SDKs (no framework initially) |
| Queue | Redis + Celery (arq as lighter alternative) |
| DB | PostgreSQL 16 + pgvector, SQLAlchemy 2.0, Alembic |
| GitHub integration | GitHub App JWT flow, PyGithub/httpx |
| Workspace Provisioner (Phase 1) | Python, docker-py, local Docker |
| Workspace Provisioner (Phase 2) | Go, Docker SDK for Go, client-go, gRPC |
| Containerization | Docker + Docker Compose |
| Testing | pytest, pytest-asyncio, testcontainers; Go: testing + testify |
| Lint/Type | ruff, mypy strict; golangci-lint |
| CI/CD | GitHub Actions → GHCR |
| Observability | OpenTelemetry, structlog, Prometheus, Grafana, Loki |
| Optional local UI | TypeScript, Next.js, React, Tailwind |

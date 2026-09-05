# Open Source AI Code Reviewer & Coding Agent — Architecture

## Overview

A self-hosted, Docker-containerized system for AI-assisted code review and
autonomous coding tasks. The operator brings their own model provider(s),
their own domain datasource, and their own infrastructure (VPS/K8s). The
project provides the orchestration: review automation, an async coding
agent, and a debuggable, on-demand workspace for that agent to work in.

Three subsystems, deliberately decoupled:

1. **Review Engine** — event-driven, stateless. Reacts to GitHub PR/issue
   events and posts review comments.
2. **Coding Agent** — async task queue consumer. Takes an assigned task,
   plans, edits code inside a live workspace, opens a PR.
3. **Workspace Provisioner** — owns the lifecycle of the containerized
   dev environment the agent (and human debugger) works in.

They are independently deployable services in a single monorepo, sharing
common libraries rather than a runtime.

---

## Repository Layout

```
/services
  /review-engine           # event-driven, stateless workers
  /coding-agent             # async task queue consumer, agent loop
  /workspace-provisioner    # VPS/container lifecycle manager
  /model-gateway            # unified model interface + adapters
  /api-gateway              # auth, webhooks in, REST/GraphQL out

/packages
  /agent-core                # shared: tool-use loop, planning, memory
  /github-integration         # shared: PR/issue/webhook client
  /datasource-connectors      # shared: pluggable domain data (vector DB, docs, code index)
  /common                     # types, config, logging, telemetry

/infra
  /docker                    # per-service Dockerfiles
  /compose or /helm           # deployment manifests
```

Each service has its own Dockerfile, own deploy, own scaling knobs. Shared
logic lives in `/packages` and is versioned/imported, never duplicated.

---

## Subsystem 1: Review Engine

**Nature:** stateless, horizontally scalable, purely event-driven.

**Flow:**
1. GitHub sends a webhook (PR opened/updated, comment added) to
   `api-gateway`.
2. `api-gateway` verifies the webhook signature, enqueues a job (Redis /
   RabbitMQ / NATS — pluggable).
3. A `review-engine` worker picks up the job:
   - Fetches the diff via `github-integration`.
   - Builds context: changed files, relevant surrounding code, plus
     retrieval results from the configured `DatasourceConnector` (the
     operator's domain knowledge base — vector store, internal docs,
     style guide, etc.).
   - Calls `model-gateway` to generate review comments.
   - Posts results back to GitHub (inline comments + summary) via
     `github-integration`.

**Key property:** no persistent workspace required. A review worker never
needs to execute code — it reasons over diffs and retrieved context. This
is why it must not share a runtime with the agent, which does need live
compute.

---

## Subsystem 2: Coding Agent

**Nature:** async, task-queue driven. Long-running, stateful per task.

**Flow:**
1. Trigger: an issue is assigned to the bot, or a task is submitted
   directly via API/CLI. Enqueued as a job.
2. A `coding-agent` worker picks up the task and runs the agent loop
   (implemented once, in `packages/agent-core`, imported here):
   - **Plan** — break the task into steps.
   - **Retrieve** — pull relevant context via the same
     `DatasourceConnector` interface used by the Review Engine.
   - **Provision** — request a workspace from `workspace-provisioner`.
   - **Act** — execute tool calls inside that workspace: read/write
     files, run tests, run shell commands, inspect output.
   - **Iterate** — repeat plan/act until the task is complete or a step
     budget is hit.
   - **Ship** — commit changes, open a PR via `github-integration`.
   - **Teardown** — release or checkpoint the workspace.
3. Task state (plan, tool-call history, current step) is persisted in
   Postgres — not held only in worker memory — so a crashed worker can
   resume rather than losing progress.

**Key property:** this is the only subsystem that needs live compute
during execution. That need is fully delegated to the Workspace
Provisioner, keeping the agent loop itself infrastructure-agnostic.

---

## Subsystem 3: Workspace Provisioner

**Nature:** lifecycle manager for containerized dev environments.

**Interface (stable across drivers):**
```
create(repo, ref)          -> workspace_id
exec(workspace_id, cmd)    -> output
attach(workspace_id)       -> ssh/terminal endpoint
destroy(workspace_id)      -> ack
```

**Drivers (pluggable):**
- Local Docker (default, single-node self-host).
- Operator's own VPS.
- Operator's own Kubernetes cluster.

**Debuggability:** `attach()` exposes a live entry point (web terminal or
SSH) into the exact container the agent is using, so a human can inspect
filesystem state and running processes in real time — not just after the
fact via logs. This is a core differentiator of the product and should be
treated as a first-class feature, not an afterthought.

**Note:** the interface here is intentionally identical to what the
managed offering will use, so only the driver changes between OSS
self-hosting and the managed product — the provisioner contract, the
agent loop, and everything above it stay the same.

---

## Model Gateway (shared)

**Design decision: a thin, self-owned unified interface — not a hard
dependency on a third-party universal shim.**

Rationale:
- Operators will bring very different providers: Anthropic, OpenAI,
  Azure OpenAI, Bedrock, or local OpenAI-compatible servers (vLLM,
  Ollama). Both the Review Engine and Coding Agent need to code against
  one contract, or every feature becomes an N-way branch across two
  subsystems.
- Coding agents lean on provider-specific capabilities: extended
  thinking, prompt caching, native tool-use formats, large context
  windows. A lowest-common-denominator "chat completion only" shim
  quietly degrades agent quality.

**Approach:**
- Define an internal `ModelProvider` interface: `generate`, `stream`,
  `tool_call`, `embed`, `capabilities()`.
- Implement adapters per provider (Anthropic, OpenAI, Bedrock, Azure,
  generic OpenAI-compatible/local).
- Maintain a capability registry (`supports_prompt_caching`,
  `supports_parallel_tool_calls`, `max_context`, etc.) so the agent and
  router can make informed decisions rather than assuming uniform
  behavior.
- Where a provider's basic chat/completion behavior is already well
  standardized, wrapping an existing library (e.g. LiteLLM) *inside* a
  single adapter is fine — but that abstraction must not leak into
  `agent-core` as the primary interface.

---

## Datasource Connectors (shared)

Pluggable interface for "bring your own domain knowledge":

```
DatasourceConnector:
  index(source)      # ingest docs/code/wiki into a queryable store
  query(text, k)      -> relevant chunks
```

Operators configure one or more connectors (pgvector, Pinecone, plain
file glob + embeddings, internal wiki API, etc.). Both the Review Engine
and Coding Agent query the same connector interface before building
prompts — domain context should not be duplicated or diverge between the
two subsystems.

---

## Cross-Cutting Concerns

- **api-gateway**: single ingress point. Webhook signature verification,
  auth, rate limiting, routes requests into the appropriate queue.
- **Configuration**: model provider, datasource, GitHub App credentials,
  and infra driver are all configured via file + environment variables.
  No hardcoded provider or infra assumptions anywhere in `agent-core` or
  `review-engine` — this is what makes the project genuinely
  self-hostable with arbitrary providers.
- **Queueing**: pluggable (Redis/RabbitMQ/NATS), used by both the Review
  Engine and Coding Agent, with independent consumer groups per service.
- **Observability**: structured logs and traces keyed by task/job ID.
  Understanding *why* the agent took a given action is core UX, not a
  nice-to-have — this ties directly into the workspace's live-attach
  debuggability.

---

## Design Principles Recap

1. **Separate runtime characteristics, separate services.** Stateless
   event handling (review) must not share a deployable with a stateful
   agent loop that needs live compute.
2. **One shared agent loop, not two.** `agent-core` is a library used by
   `coding-agent`; logic is never forked between OSS and managed.
3. **Stable internal interfaces at the seams that will change.** The
   Workspace Provisioner interface and the Model Gateway interface are
   designed so that only their *drivers/adapters* differ between
   self-hosted and managed deployments — not the calling code.
4. **Nothing hardcoded about provider or infra.** Every external
   dependency (model, datasource, compute) is configuration, not code.

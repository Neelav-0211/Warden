# Spec 14: Observability

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 02 (base), 12, 13 (instrumentation targets)
- **Owns**: tracing/logging instrumentation across services, `/infra/
  compose`'s observability profile

## Goal

Make "why did the agent do X" answerable from traces, not just logs —
called out in the architecture doc as core UX, not a nice-to-have — and
give operators a local Prometheus/Grafana/Loki stack out of the box.

## Scope

- **Tracing instrumentation**: every step of `AgentSession` (plan, each
  tool call, ship, teardown) emits a span carrying `task_id`, `step_index`,
  tool name/args (redacted if sensitive), and outcome. `review-engine`
  emits spans per job (context-build, generate, post).
- **Correlation**: every log line and span is tagged with `task_id`/
  `job_id`, bound via `common.logging.bind_context` (spec 02), so logs
  and traces can be cross-referenced in Grafana/Loki.
- **Metrics**: job throughput, job failure rate, agent step count
  distribution, model call latency/cost (token counts) per provider —
  exported via OpenTelemetry metrics or a Prometheus client, operator's
  choice documented here.
- **Compose observability profile**: `docker compose --profile
  observability up` brings up Prometheus + Grafana (with a pre-built
  dashboard JSON checked into `/infra`) + Loki, wired to scrape/receive
  from all services.

## Non-Goals

- No hosted/managed observability backend — this is the self-host local
  stack only.

## TDD Plan

1. `test_span_attributes.py` (unit, in-memory OTel exporter): running a
   scripted `AgentSession` step emits a span with the required attributes
   (`task_id`, `step_index`, tool name) — assert against the in-memory
   span exporter, no real collector needed.
2. `test_log_trace_correlation.py` (unit): a log emitted inside a traced
   span carries the same `trace_id`/`task_id` as the span — verified via
   `structlog` capture + in-memory span exporter.
3. `test_metrics_emission.py` (unit, in-memory metrics reader): a
   scripted job run increments the expected counters/histograms by the
   expected amount.
4. `test_compose_observability_profile_integration.py` (integration/
   manual-checklist): `docker compose --profile observability up`
   succeeds; Prometheus target list shows all services `up`; the
   pre-built Grafana dashboard loads without a "no data" panel after a
   scripted job runs.

## Acceptance Criteria

- [ ] Every `AgentSession` step and every `review-engine` job phase emits
      a span with the documented attributes, verified by test against an
      in-memory exporter.
- [ ] Logs and traces share a correlation id, verified by test.
- [ ] Core metrics (throughput, failure rate, step count, model latency)
      are emitted and verified by test.
- [ ] `docker compose --profile observability up` succeeds and the
      checked-in Grafana dashboard shows real data after a scripted job,
      verified manually and recorded as a checklist item in this spec
      until an automated smoke test exists.

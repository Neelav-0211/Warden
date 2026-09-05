# Spec 19: Dashboard / Local UI (Optional)

- **Status**: Not Started
- **Phase**: 3 (optional)
- **Depends on**: 11
- **Owns**: `services/dashboard/` (or a top-level `/apps/dashboard`)

## Goal

An optional read/light-write UI for reviewing agent runs and browsing
workspace sessions, talking to `api-gateway` over REST only — no shared
runtime with the Python services, so it can be skipped entirely for a
pure API/webhook self-host.

## Scope

- **TypeScript + Next.js + React + TailwindCSS**, per the tech-stack doc.
- Pages: task list (status, filters), task detail (plan, step timeline,
  tool-call log — reads from the same data `GET /tasks/{id}` exposes,
  possibly extended with a richer detail endpoint if spec 11's contract
  needs a superset for this), review record list/detail, and a live
  workspace attach view (embeds/links to the `attach()` endpoint from
  spec 09/17 for a given in-progress task).
- Auth: reuses `api-gateway`'s API key for now (simplest v1 — a proper
  session/login flow is future work if multi-user access is needed).
- No server-side business logic — purely a client of `api-gateway`'s
  REST API; any new data needs must be added as new `api-gateway`
  endpoints (a small addendum to spec 11), not computed in the dashboard
  itself.

## Non-Goals

- No new backend logic embedded in the Next.js app (e.g. no direct DB or
  queue access) — keeps the "no shared runtime" property from the
  architecture doc's tech stack.
- No multi-user auth/roles in v1.

## TDD Plan

- **Unit**: component tests (React Testing Library) for the task list/
  detail/review views against a mocked API client — loading, empty,
  error, and populated states each get an explicit test.
- **API client contract tests**: a typed client (generated from
  `api-gateway`'s OpenAPI schema, spec 11) is tested against a mocked
  server built from that same schema, so client/server drift is caught
  automatically when the schema changes.
- **E2E** (Playwright): boot `api-gateway` (real, against test fixtures)
  + the dashboard dev server; verify a task submitted via the API appears
  in the list and its detail view updates as status changes (poll-based).

## Acceptance Criteria

- [ ] Task list/detail and review list/detail pages render correctly for
      loading/empty/error/populated states, verified by component tests.
- [ ] Generated API client stays in sync with `api-gateway`'s OpenAPI
      schema, verified by a contract test that fails on drift.
- [ ] Playwright E2E: a task created via direct API call becomes visible
      in the dashboard and reflects status changes without a page reload
      (polling or websocket, implementer's choice, documented here).
- [ ] Dashboard has zero direct DB/queue dependencies — verified by
      dependency audit (no `psycopg`/`redis` packages in its
      `package.json`/lockfile).
- [ ] Live workspace attach view successfully embeds/links to a real
      `attach()` endpoint for an in-progress task, verified manually
      against a running self-host stack (spec 15).

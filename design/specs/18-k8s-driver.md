# Spec 18: Kubernetes Driver

- **Status**: Not Started
- **Phase**: 2 (stretch — only needed once the managed offering or a
  self-hoster on K8s needs it; not required to consider Phase 2 "done")
- **Depends on**: 17
- **Owns**: `services/workspace-provisioner/` (adds a driver, no interface
  change)

## Goal

A second `WorkspaceDriver` implementation (Go), backed by `client-go`,
proving the interface genuinely abstracts over infra as the architecture
doc requires ("only the driver changes between OSS self-hosting and the
managed product").

## Scope

- `K8sDriver` implementing the same Go interface from spec 17: `create`
  provisions a Pod (+ any supporting Service/ConfigMap for repo checkout),
  `exec` uses the Kubernetes exec subresource, `attach` streams via the
  same subresource's attach/exec streaming, `destroy` deletes the Pod.
- Config-driven driver selection (local Docker vs. K8s), same pattern as
  every other pluggable interface in this project.
- Namespacing/isolation: each workspace gets its own Pod with resource
  requests/limits matching spec 09's CPU/memory cap semantics.

## Non-Goals

- No multi-cluster/multi-tenant scheduling logic — single cluster,
  single namespace (or configurable namespace) per operator.

## TDD Plan

1. Run the **same** ported contract test suite from spec 17 against
   `K8sDriver`, using `envtest`/`kind` (a real ephemeral cluster in CI) —
   this is the point of the contract suite: zero new test-writing for
   basic behavior, only environment setup changes.
2. `TestResourceLimitsAppliedToPod`: assert Pod spec has the configured
   CPU/memory requests/limits.
3. `TestAttachStreamingOverK8sExec`: assert `attach()` streams real
   output from a running Pod via the exec subresource.
4. `TestNamespaceIsolation`: two workspaces in different configured
   namespaces don't see each other's Pods when listing/reconciling.

## Acceptance Criteria

- [ ] `K8sDriver` passes the same ported contract test suite as the
      local Docker driver, run against a real ephemeral cluster (`kind`)
      in CI.
- [ ] Resource limits and namespace isolation verified by test.
- [ ] Driver selection is a config value; `coding-agent`/`agent-core`
      require no code changes to switch drivers, verified by running
      spec 10's tool tests unmodified against the K8s-backed driver via
      the same adapter used in spec 17.

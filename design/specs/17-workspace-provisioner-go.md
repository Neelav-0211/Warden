# Spec 17: Workspace Provisioner Rewrite (Go)

- **Status**: Not Started
- **Phase**: 2
- **Depends on**: 09 (interface + contract test suite must be stable and
  proven in production/self-host use before porting)
- **Owns**: `services/workspace-provisioner/` (Go rewrite, replaces the
  Python implementation as the running service; the Python driver's
  contract test suite is ported, not the implementation)

## Goal

Port the proven `create/exec/attach/destroy` contract to Go, behind a
gRPC service, without changing the contract itself or anything that
calls it (`coding-agent` only changes its transport, not its usage
pattern).

## Scope

- Go interface mirroring spec 09's `WorkspaceDriver` exactly:
  `Create(repo, ref) (WorkspaceHandle, error)`, `Exec(workspaceID, cmd)
  (ExecResult, error)`, `Attach(workspaceID) (stream, error)`,
  `Destroy(workspaceID) error`.
- `LocalDockerDriver` (Go) using `docker/docker/client`, functionally
  equivalent to the Python version.
- **gRPC service** (`google.golang.org/grpc` + protobuf) exposing
  `Create`, `Exec`, `Attach` (server-streaming, for live terminal
  output), `Destroy`. `.proto` file checked in, versioned.
- `coding-agent` (Python) gains a gRPC client to this service, replacing
  its in-process/library call to the Python driver from spec 09 — this
  is the one integration point that changes on the Python side; document
  the migration explicitly.
- Ported contract test suite: the same behavioral assertions from spec
  09's `contract_test_workspace_driver.py`, rewritten in Go `testing` +
  `testify`, run against the Go `LocalDockerDriver`.

## Non-Goals

- No Kubernetes driver yet (spec 18).
- No change to the *interface's meaning* — if the Go port reveals the
  Python-era contract was wrong/incomplete, that's a revision to spec 09
  first, then ported, not a silent divergence.

## TDD Plan

1. Write the `.proto` file and generate stubs first; write a trivial
   `TestGRPCServiceBoots` that starts the server and calls a health/
   reflection RPC — proves the scaffold before real logic.
2. Port spec 09's contract test suite to Go table-driven tests using
   `testify/suite`, initially run against a stub/no-op driver to confirm
   the test suite itself compiles and runs (red).
3. Implement `LocalDockerDriver` in Go, iterating until the ported
   contract suite is green — same order as spec 09 (create → exec →
   attach → destroy → resource limits → registry reconciliation).
4. `dockertest`-based integration tests for real-Docker-daemon behavior,
   mirroring spec 09's integration tests.
5. `TestAttachStreaming`: gRPC server-streaming `Attach` delivers output
   chunks in order to a client, and closes cleanly on `Destroy`.
6. Python-side: `test_grpc_client_integration.py` in `coding-agent`,
   asserting its gRPC client against the real Go service satisfies the
   same behavioral expectations `agent-core`'s tools (spec 10) rely on —
   i.e. swapping the transport is invisible to `agent-core`.

## Acceptance Criteria

- [ ] Go `LocalDockerDriver` passes the fully ported contract test suite,
      matching spec 09's behavioral guarantees one-for-one.
- [ ] gRPC `Attach` streams live output and terminates cleanly on
      `Destroy`, verified by test.
- [ ] `coding-agent`'s tool implementations (spec 10) require zero
      changes beyond swapping the driver's transport client — verified
      by running spec 10's existing tool tests against the gRPC-backed
      driver via a thin adapter.
- [ ] `golangci-lint` passes on the new service.
- [ ] Old Python driver/service code is removed (not left as dead code)
      once the Go service is confirmed at parity in a staging self-host
      run.

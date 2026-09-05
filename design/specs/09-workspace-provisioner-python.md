# Spec 09: Workspace Provisioner (Python / Local Docker Driver)

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 02
- **Owns**: `services/workspace-provisioner/`

## Goal

Implement the stable `create/exec/attach/destroy` interface from the
architecture doc, with a local-Docker driver, defined as an explicit
Python `Protocol`/ABC so the Phase 2 Go rewrite (spec 17) has an exact
contract to port against.

## Scope

- `WorkspaceDriver` `Protocol`: `create(repo, ref) -> WorkspaceHandle`,
  `exec(workspace_id, cmd) -> ExecResult`, `attach(workspace_id) ->
  AttachEndpoint`, `destroy(workspace_id) -> None`.
- `LocalDockerDriver` implementing it via `docker-py`: clones/mounts the
  repo at `ref` into a fresh container, runs commands via `docker exec`
  equivalent, tears the container down on `destroy`.
- **Debug attach**: `ttyd`-based (or `websocat`) web terminal bridge
  exposed per-workspace; `attach()` returns a connection endpoint (URL or
  socket path) a human can open live — this is called out in the
  architecture doc as a first-class feature, so it needs its own explicit
  test, not just "container exists."
- Workspace registry: which workspace IDs are live, mapped to container
  IDs — persisted (via `common.db`, reusing spec 03's `Job`-style
  bookkeeping or a dedicated `Workspace` table if needed) so a restarted
  provisioner service can reconcile against actually-running containers
  rather than losing track of them.
- Resource limits on created containers (CPU/memory caps, no-network
  option) — configurable, sane defaults.
- The contract test suite for `WorkspaceDriver` (per spec 00's rule),
  which the Go driver (spec 17) will also be run against conceptually
  (ported, since it's a different language) to prove parity.

## Non-Goals

- No gRPC/REST service wrapper around this yet if `coding-agent` can call
  it in-process as a library in Phase 1 — confirm this against spec 13
  when reached; if `coding-agent` needs it out-of-process even in Phase
  1, add a minimal FastAPI wrapper here (mark decision below once made).
- No Kubernetes driver (spec 18) or VPS driver — local Docker only.

## Public Interface

```python
class WorkspaceHandle(BaseModel):
    workspace_id: str
    repo: str
    ref: str
    status: Literal["provisioning", "ready", "destroyed"]

class ExecResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str

class WorkspaceDriver(Protocol):
    async def create(self, repo: str, ref: str) -> WorkspaceHandle: ...
    async def exec(self, workspace_id: str, cmd: list[str]) -> ExecResult: ...
    async def attach(self, workspace_id: str) -> AttachEndpoint: ...
    async def destroy(self, workspace_id: str) -> None: ...
```

## TDD Plan

1. `contract_test_workspace_driver.py` (shared): `create` returns a
   handle with status transitioning to `ready`; `exec` of a known command
   (e.g. `echo hello`) returns expected stdout/exit code; `exec` against
   a nonexistent `workspace_id` raises `NotFoundError`; `destroy` then
   `exec` on the same id raises `NotFoundError`; `attach` returns a
   reachable endpoint while the workspace is `ready` and fails cleanly
   once `destroyed`.
2. `test_local_docker_driver_integration.py`: run the contract suite
   against `LocalDockerDriver` with a real Docker daemon (CI must have
   Docker-in-Docker or socket access — document requirement).
3. `test_resource_limits_integration.py`: assert a container created via
   `create()` has the configured CPU/memory limits applied (inspect
   container config).
4. `test_attach_endpoint_integration.py`: assert the `ttyd`/`websocat`
   bridge is actually reachable (open a connection, send a trivial
   command, read output) — proving debuggability end-to-end, not just
   that a container exists.
5. `test_registry_reconciliation_integration.py`: create two workspaces,
   simulate a provisioner restart (new driver instance, same DB), assert
   it can list live workspaces and their container mappings correctly
   without leaking or double-tracking.

## Acceptance Criteria

- [ ] `WorkspaceDriver` Protocol defined; `LocalDockerDriver` passes the
      full contract test suite against a real Docker daemon.
- [ ] `attach()` produces a live, connectable terminal endpoint into the
      running container, verified by an automated test that sends a
      command through it and reads real output back.
- [ ] Resource limits (CPU/memory) are applied and verified by inspecting
      the created container's actual config.
- [ ] Workspace registry survives a provisioner restart with correct
      reconciliation, verified by test.
- [ ] `exec`/`attach`/`destroy` against an unknown or already-destroyed
      workspace id raise typed errors, never silently no-op.
- [ ] Decision recorded here on in-process-library vs. thin-service
      wrapper for Phase 1, with rationale, once spec 13 confirms the
      calling pattern.

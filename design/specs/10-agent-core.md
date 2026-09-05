# Spec 10: Agent Core (`packages/agent-core`)

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 03, 05, 06, 07, 09
- **Owns**: `packages/agent-core/`

## Goal

The single, shared agent loop (plan → retrieve → provision → act →
iterate → ship → teardown) used by `coding-agent` (and structurally
available for reuse by any future subsystem) — implemented once, never
forked.

## Scope

- **Planner**: takes a task description + retrieved context, calls the
  Model Gateway (`tool_call` or structured `generate`) to produce a
  step-by-step plan (structured Pydantic output, not free text parsing).
- **Tool-use loop**: a registry of tools the agent can call (`read_file`,
  `write_file`, `run_command`, `run_tests`) — each tool wraps a
  `WorkspaceDriver.exec` call (spec 09) plus tool-specific
  argument/result schemas. Loop: ask model for next tool call → execute
  against workspace → feed observation back → repeat until plan
  complete, `finish` tool called, or step budget exceeded.
- **Step budget / termination conditions**: max steps, max wall-clock
  time, explicit "give up and report" path when budget is hit instead of
  looping forever.
- **State persistence**: every plan step, tool call, and observation is
  written to `TaskStep` (spec 03) as it happens, not batched at the end —
  this is what makes a crashed worker resumable. `AgentSession.resume(task_id)`
  reconstructs in-memory state from persisted `TaskStep` rows.
- **Ship step**: on plan completion, commits changes and opens a PR via
  `github-integration` (spec 08).
- **Teardown**: calls `WorkspaceDriver.destroy` (or checkpoints, if a
  later spec adds checkpoint support) unconditionally on loop exit
  (success, failure, or budget exhaustion) — verified via a
  try/finally-style guarantee, not best-effort.

## Non-Goals

- No queue consumption logic (that's `coding-agent`, spec 13, which
  invokes `AgentSession.run`/`resume`) — `agent-core` is a library with
  no knowledge of Celery/Redis.

## Public Interface

```python
class AgentSession:
    def __init__(self, task_id: str, model: ModelProvider, connector: DatasourceConnector,
                 workspace: WorkspaceDriver, github: GitHubClient, tools: ToolRegistry,
                 budget: StepBudget) -> None: ...
    async def run(self) -> AgentResult: ...
    @classmethod
    async def resume(cls, task_id: str, ...) -> "AgentSession": ...

class ToolRegistry:
    def register(self, name: str, schema: type[BaseModel], handler: ToolHandler) -> None: ...

class StepBudget(BaseModel):
    max_steps: int
    max_wall_clock_seconds: int
```

## TDD Plan

Build and test each piece in isolation with fakes before assembling the
full loop:

1. `test_planner.py` (unit, `FakeModelProvider` from spec 05): given a
   scripted model response, planner produces the expected structured
   plan; malformed model output raises a typed error rather than
   crashing downstream.
2. `test_tool_registry.py` (unit): registering and invoking tools
   validates arguments against the declared schema; invoking an
   unregistered tool raises `NotFoundError`.
3. `test_tools_read_write_run.py` (unit, fake `WorkspaceDriver`): each
   built-in tool translates its arguments into the correct
   `WorkspaceDriver.exec` call and parses the result correctly.
4. `test_step_budget.py` (unit): loop halts exactly at `max_steps`; a
   fake clock proves wall-clock budget halts the loop without waiting
   real time in tests.
5. `test_state_persistence_integration.py` (integration, real DB from
   spec 03): run a scripted short session, assert every step is
   persisted incrementally (not just at the end) by checking DB state
   mid-run (pause via a test hook/fake tool).
6. `test_resume_integration.py`: run a session partway, simulate a crash
   (drop the in-memory object), call `AgentSession.resume(task_id)`,
   assert it continues from the correct step without repeating
   completed ones.
7. `test_full_loop_integration.py` (integration, `FakeModelProvider` +
   real `LocalDockerDriver` from spec 09 + real DB): end-to-end scripted
   task (e.g. "add a function and make a failing test pass") runs plan →
   act → ship against a disposable test repo, opens a PR (using a fake/
   test GitHub client or a real disposable repo — decide and document),
   and tears down the workspace.
8. `test_teardown_guarantee.py`: force an exception mid-loop (e.g. a tool
   raises unexpectedly), assert `WorkspaceDriver.destroy` is still called
   exactly once.

## Acceptance Criteria

- [ ] Full plan→act→ship→teardown loop runs end-to-end against fakes/
      local Docker in an integration test, producing a PR-ready commit
      on a disposable repo.
- [ ] Every step is persisted incrementally, verified by test inspecting
      DB state mid-run.
- [ ] `resume()` correctly continues an interrupted session without
      duplicating already-completed steps, verified by test.
- [ ] Step budget (count and wall-clock) is enforced and verified by
      test using a fake clock — no real waiting in the test suite.
- [ ] Workspace teardown is guaranteed on every exit path (success,
      failure, budget exhaustion), verified by test for at least the
      failure path.
- [ ] `agent-core` has zero imports of Celery/Redis/FastAPI — verified by
      a dependency/import lint check, keeping it a pure library.

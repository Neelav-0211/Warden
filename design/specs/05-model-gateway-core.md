# Spec 05: Model Gateway — Core Interface

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 02
- **Owns**: `services/model-gateway/core/` (interface, capability registry,
  router) — adapters themselves are spec 06.

## Goal

Define the internal `ModelProvider` contract and capability registry
described in the architecture doc, plus a fully working in-memory fake
adapter, before any real provider is wired up. This lets `agent-core`
(spec 10), `review-engine` (spec 12), and `coding-agent` (spec 13) all be
built and tested against a stable, deterministic model interface.

## Scope

- `ModelProvider` `Protocol`: `generate`, `stream`, `tool_call`, `embed`,
  `capabilities()`.
- `Capabilities` dataclass/Pydantic model: `supports_prompt_caching`,
  `supports_parallel_tool_calls`, `max_context_tokens`,
  `supports_streaming`, `supports_embeddings`.
- Structured request/response types (Pydantic): `GenerateRequest`,
  `GenerateResponse`, `ToolCallRequest`, `ToolCallResponse`,
  `EmbedRequest`, `EmbedResponse` — provider-agnostic shapes that
  adapters translate to/from.
- A capability-aware router: `ModelGatewayRouter.select(requirements:
  Capabilities) -> ModelProvider`, given a configured set of providers,
  picks (or rejects with a clear error) based on required capabilities.
- `FakeModelProvider`: a deterministic in-memory adapter (scripted
  responses, canned tool calls) implementing the full `ModelProvider`
  contract — used as the default for all downstream unit tests so no
  other spec's test suite needs real API keys or network access.
- The **contract test suite** for `ModelProvider` (per spec 00's
  cross-cutting rule): behavior every adapter must satisfy (e.g.
  `generate` respects `max_tokens`, `tool_call` returns well-formed
  structured output matching the requested schema, `capabilities()` is
  pure/side-effect-free).

## Non-Goals

- No real provider adapters (Anthropic/OpenAI/etc.) — spec 06.
- No retry/backoff-across-providers routing logic beyond capability
  selection (basic per-adapter retry/backoff is part of spec 06, since
  it's provider-specific, e.g. rate-limit header handling).

## Public Interface

```python
class Capabilities(BaseModel):
    supports_prompt_caching: bool
    supports_parallel_tool_calls: bool
    max_context_tokens: int
    supports_streaming: bool
    supports_embeddings: bool

class ModelProvider(Protocol):
    async def generate(self, req: GenerateRequest) -> GenerateResponse: ...
    def stream(self, req: GenerateRequest) -> AsyncIterator[GenerateChunk]: ...
    async def tool_call(self, req: ToolCallRequest) -> ToolCallResponse: ...
    async def embed(self, req: EmbedRequest) -> EmbedResponse: ...
    def capabilities(self) -> Capabilities: ...

class ModelGatewayRouter:
    def __init__(self, providers: dict[str, ModelProvider]) -> None: ...
    def select(self, requirements: Capabilities) -> ModelProvider: ...
```

## TDD Plan

1. `test_types.py` (unit): Pydantic request/response models validate
   correctly and reject malformed input (e.g. negative `max_tokens`).
2. `contract_test_model_provider.py` (shared, parametrized over
   `FakeModelProvider` now, real adapters in spec 06): `generate` returns
   non-empty content for a scripted prompt; `tool_call` returns a
   response whose `arguments` validate against the requested JSON
   schema; `capabilities()` called twice returns an equal value
   (pure); `stream` yields chunks that concatenate to the same content
   `generate` would return for an equivalent scripted request.
3. `test_fake_provider.py`: script a canned response, assert
   `FakeModelProvider` returns exactly it — proving the fake is usable as
   a deterministic test double by downstream specs.
4. `test_router.py`: given providers with different `Capabilities`,
   assert `select` returns the correct provider for a requirement set,
   and raises a clear `WardenError` subclass (e.g. `NoCapableProviderError`)
   when none qualify.

## Acceptance Criteria

- [ ] `ModelProvider` Protocol and all request/response types are defined,
      typed, and documented.
- [ ] `FakeModelProvider` passes the full contract test suite.
- [ ] `ModelGatewayRouter.select` correctly filters by every field in
      `Capabilities`, verified by test per field.
- [ ] `select` with no qualifying provider raises a typed, catchable
      error (not a bare `KeyError`/`None`).
- [ ] Every downstream spec (10, 12, 13) can run its full unit test suite
      using only `FakeModelProvider` — no network, no API keys required
      for `pytest -m unit`.

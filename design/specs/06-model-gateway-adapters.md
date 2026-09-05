# Spec 06: Model Gateway — Provider Adapters

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 05
- **Owns**: `services/model-gateway/adapters/`

## Goal

Implement real `ModelProvider` adapters for the providers operators are
expected to bring, each passing the contract test suite defined in
spec 05.

## Scope

Implement one adapter at a time, in this order (each is its own
mergeable slice, not a single big PR):

1. **Anthropic adapter** — native SDK, tool-use format, prompt caching,
   extended thinking passthrough where the `GenerateRequest` requests it.
2. **OpenAI adapter** — native SDK, function-calling format.
3. **Generic OpenAI-compatible adapter** — `httpx`-based, targets local
   servers (vLLM/Ollama) and anything speaking the OpenAI HTTP schema;
   this is also the fallback documented for operators with no listed
   adapter.
4. **Bedrock adapter** and **Azure OpenAI adapter** — lower priority,
   same pattern.

Each adapter:
- Declares accurate `capabilities()` (real `max_context_tokens` per
  model, real prompt-caching/parallel-tool-call support).
- Translates provider-specific errors (rate limit, context-length
  exceeded, auth failure) into `common.errors.ExternalServiceError`
  subtypes so callers don't need provider-specific exception handling.
- Implements its own retry/backoff for transient failures (rate limits,
  5xx) with jitter, configurable via `common.config`.

## Non-Goals

- No cross-provider fallback/routing beyond spec 05's capability
  selection (e.g. no "try Anthropic, fall back to OpenAI on failure" —
  that's a product decision for a later spec if ever needed).

## TDD Plan

For **each** adapter, in order:

1. Write adapter-specific unit tests against a mocked HTTP layer
   (`respx` for `httpx`-based adapters, SDK's own test/mock utilities or
   `unittest.mock` for SDK-based ones) covering: request translation
   (`GenerateRequest` → provider payload), response translation (provider
   response → `GenerateResponse`), and error translation (provider error
   → `ExternalServiceError` subtype).
2. Run the shared contract test suite from spec 05 against the adapter
   with the HTTP layer mocked to behave like a real endpoint (scripted
   fixture responses recorded from real API docs/examples).
3. Add one opt-in, explicitly-skipped-by-default `integration` test per
   adapter that hits the real API — gated behind an env var
   (`RUN_LIVE_MODEL_TESTS=1`) and a real key, never run in CI by default
   (cost/flakiness), but available for manual verification.
4. Add a rate-limit/retry test: mock a 429 then a success, assert the
   adapter retries and returns the successful result; mock persistent
   429s, assert it gives up after configured max attempts and raises.

## Acceptance Criteria

- [ ] Anthropic and OpenAI adapters both pass the full spec 05 contract
      test suite against mocked HTTP/SDK layers.
- [ ] Generic OpenAI-compatible adapter passes the contract suite against
      a mocked local-server response, proving vLLM/Ollama compatibility
      by shape.
- [ ] Every adapter's `capabilities()` values are backed by a citation/
      comment referencing the source (provider docs) they were taken
      from — no guessed numbers.
- [ ] Rate-limit retry/backoff behavior verified by test for at least one
      adapter (pattern reused for others).
- [ ] All provider errors surface as `ExternalServiceError` subtypes to
      callers — verified by test that no raw provider SDK exception
      escapes the adapter.
- [ ] Live integration tests exist but are excluded from default/CI runs,
      confirmed by checking CI logs show zero live-adapter tests executed
      without the opt-in env var.

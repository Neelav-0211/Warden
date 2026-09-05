# Spec 08: GitHub Integration

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 02
- **Owns**: `packages/github-integration/`

## Goal

One shared client for everything GitHub: App auth, webhook signature
verification, and PR/issue/comment operations — used identically by
`api-gateway`, `review-engine`, and `coding-agent`.

## Scope

- **GitHub App auth flow**: JWT generation from the App's private key,
  exchange for an installation access token, token caching with
  expiry-aware refresh (implemented directly per the tech-stack decision
  to understand the flow, not hidden behind a library).
- **Webhook signature verification**: `verify_signature(payload_bytes,
  signature_header, secret) -> bool` using HMAC-SHA256, stdlib only.
  Must use constant-time comparison (`hmac.compare_digest`) — this is a
  security-sensitive function and gets its own explicit test for timing-
  safe comparison usage.
- **PR/issue/comment client**: thin wrapper (PyGithub or raw `httpx`
  against REST/GraphQL — pick one, document the decision here) exposing:
  `get_pull_request_diff`, `post_review_comment` (inline + summary),
  `list_changed_files`, `get_issue`, `create_pull_request`,
  `create_branch`, `push_commit`.
- Rate-limit awareness: surfaces GitHub's rate-limit headers, backs off
  automatically on `403`/secondary rate limit responses.

## Non-Goals

- No webhook *routing*/queueing (that's `api-gateway`, spec 11) — this
  spec only provides `verify_signature` for that service to call.

## Public Interface

```python
class GitHubAppAuth:
    def __init__(self, app_id: str, private_key: str) -> None: ...
    async def get_installation_token(self, installation_id: int) -> str: ...

def verify_signature(payload: bytes, signature_header: str, secret: str) -> bool: ...

class GitHubClient:
    async def get_pull_request_diff(self, repo: str, pr_number: int) -> str: ...
    async def post_review_comment(self, repo: str, pr_number: int, body: str, inline: list[InlineComment] | None = None) -> None: ...
    async def create_pull_request(self, repo: str, head: str, base: str, title: str, body: str) -> PullRequestRef: ...
```

## TDD Plan

1. `test_signature_verification.py` (unit): valid signature passes;
   tampered payload fails; wrong secret fails; assert the implementation
   uses `hmac.compare_digest` (either via code review checklist or by
   asserting timing behavior isn't naively short-circuiting — at minimum,
   a direct source-inspection test/lint rule forbidding `==` for secret
   comparison in this file).
2. `test_app_auth.py` (unit, mocked `httpx`): JWT is generated with
   correct claims (`iss`, `exp` within GitHub's 10-minute limit); token
   exchange call is made with the right headers; cached token is reused
   until near expiry, then refreshed.
3. `test_github_client.py` (unit, mocked HTTP via `respx`): each client
   method sends the expected request shape and correctly parses a
   realistic fixture response; a `404`/`403` response raises a typed
   `ExternalServiceError`, not a raw HTTP exception.
4. `test_rate_limit_backoff.py` (unit, mocked): a `403` with rate-limit
   headers triggers a wait-and-retry using the header's reset time
   (mocked clock, no real sleep in tests).
5. `test_github_integration_live.py` (integration, opt-in via env var,
   skipped by default): exercises against a real disposable test repo —
   documented as manual/opt-in like spec 06's live adapter tests.

## Acceptance Criteria

- [ ] `verify_signature` correctly accepts valid and rejects invalid/
      tampered webhook payloads, verified by test.
- [ ] GitHub App JWT + installation token exchange implemented and unit
      tested with mocked HTTP — no real network in default test run.
- [ ] Token caching avoids refetching a still-valid token, verified by
      test asserting the mocked HTTP exchange endpoint is called exactly
      once across multiple `get_installation_token` calls within the
      expiry window.
- [ ] All GitHub client methods return typed responses and raise typed
      errors on failure — no raw provider exception or unstructured dict
      escapes the package.
- [ ] Rate-limit backoff verified by test with a mocked clock (no real
      `sleep` in the test suite).

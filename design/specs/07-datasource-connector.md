# Spec 07: Datasource Connectors

- **Status**: Not Started
- **Phase**: 1
- **Depends on**: 02, 03 (for the pgvector default, which needs Postgres)
- **Owns**: `packages/datasource-connectors/`

## Goal

Define the `DatasourceConnector` interface for "bring your own domain
knowledge" and ship the default pgvector-backed implementation, so
`review-engine` and `coding-agent` query domain context through one
shared abstraction.

## Scope

- `DatasourceConnector` `Protocol`: `index(source)`, `query(text, k)`.
- Structured types: `IndexSource` (path/glob, raw text, or URI +
  metadata), `RetrievedChunk` (content, score, source metadata).
- Default implementation: `PgVectorConnector` — uses the embedding
  function from the Model Gateway (spec 05/06, `embed()`) to embed
  content on `index()` and query on `query()`, storing vectors in the
  `pgvector` column added by spec 03's migration.
- A simple ingestion helper for the common self-hoster case: point at a
  glob of files (docs/code), chunk them (basic fixed-size or
  paragraph-based chunking — no fancy semantic chunking in v1), embed,
  store.
- Config-driven selection: which connector is active is a config value,
  not a code branch in `review-engine`/`coding-agent`.
- The contract test suite for `DatasourceConnector` (per spec 00's rule),
  parametrized so future adapters (Pinecone/Weaviate/Qdrant) reuse it.

## Non-Goals

- No Pinecone/Weaviate/Qdrant adapters in this spec — noted as future
  work, added later against the same contract test suite once there's
  real demand.

## Public Interface

```python
class DatasourceConnector(Protocol):
    async def index(self, source: IndexSource) -> IndexResult: ...
    async def query(self, text: str, k: int) -> list[RetrievedChunk]: ...

class PgVectorConnector(DatasourceConnector):
    def __init__(self, session_factory, embed_fn: Callable[[str], Awaitable[list[float]]]): ...
```

## TDD Plan

1. `test_types.py` (unit): `IndexSource`/`RetrievedChunk` validation.
2. `test_chunking.py` (unit): given a known text fixture, chunking
   produces the expected number/boundaries of chunks for both glob-file
   and raw-text sources.
3. `contract_test_datasource_connector.py` (shared): `index` then
   `query` with the same/similar text returns that content ranked above
   unrelated content (using the `FakeModelProvider`'s deterministic
   `embed()` from spec 05 so results are reproducible without a real
   embedding model); `query` with `k=N` never returns more than `N`
   results; querying an empty store returns an empty list, not an error.
4. `test_pgvector_connector_integration.py`: contract suite run against
   `PgVectorConnector` backed by the `pg_container` fixture from spec 03.
5. `test_config_selection.py`: assert changing the connector config
   value swaps the implementation `review-engine`/`coding-agent` receive,
   with no code change required in the caller (use a trivial fake caller
   for this test, since services don't exist yet).

## Acceptance Criteria

- [ ] `DatasourceConnector` Protocol and types defined and documented.
- [ ] `PgVectorConnector` passes the full contract test suite against a
      real Postgres+pgvector instance.
- [ ] Chunking behavior is deterministic and covered by unit tests with
      known fixtures.
- [ ] Connector selection is proven config-driven (test 5 above), not a
      hardcoded import in any caller.
- [ ] `query(k=N)` never returns more than `N` results and never errors on
      an empty index, verified by test.

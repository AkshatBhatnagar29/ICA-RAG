# Testing map

Unit tests cover configuration, auth/password/token logic, ingestion validation
and parsers, chunking, BM25/RRF, reranking adapters, generation/provider,
contracts/comparison/semantic extraction, agents, observability, datasets, and
UI helpers. Integration tests cover health, Redis lifecycle, and PostgreSQL
contract-analysis persistence/idempotency/tenant/FK behavior. Evaluation tests
cover retrieval metrics, citation metrics, golden schemas/metrics, regression,
and reranker experiments.

Important regression protections include:

- `tests/unit/retrieval/test_query_and_fusion.py`: scope and deterministic fusion;
- `test_reranking.py`: candidate deduplication, tie-breaking, failures;
- `tests/unit/generation/test_generation.py`: bounded context, selected-only
  citations, prompt-injection data boundary;
- `tests/unit/test_agents.py`: typed tools, cycles/timeouts, mixed namespaces;
- `tests/unit/security/test_auth.py`: tenant/RBAC/token boundaries;
- contract/integration tests: evidence, persistence, idempotency, rollback.

Safe change practice: update a focused unit test first, run its module, then
Ruff/mypy, then the full suite; run Compose-backed database/migration checks for
schema or integration changes. Host-native DB credentials are a documented
environment limitation; do not weaken authentication to make tests pass.

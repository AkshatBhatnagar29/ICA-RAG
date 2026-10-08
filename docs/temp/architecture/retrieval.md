# Phase 5 retrieval architecture

Phase 5 provides an application-owned retrieval service for the existing
PostgreSQL 16 + pgvector chunk store. It does not call an LLM, generate
answers, or rerank results.

## Flow

`query -> deterministic normalization -> required authorized scope -> dense and/or sparse retrieval -> RRF -> optional reranking -> results`

Every database query applies the tenant, document, version, and supported
metadata predicates before chunks are returned to the application. A missing
tenant scope fails closed. Complete database-enforced tenant security and
authentication/RBAC remain Phase 12 responsibilities; this service does not
pretend to replace them.

## Dense retrieval

Dense retrieval uses the Phase 4 `chunks.embedding` vector, the frozen
`intfloat/multilingual-e5-small` provider, and the existing 384-dimensional
cosine HNSW index. The provider owns E5 `query:` formatting. PostgreSQL returns
cosine distance in ascending order; the public dense score is explicitly
`1 - cosine_distance` (higher is better). Ties are ordered by stable chunk ID.

## Sparse retrieval

Sparse retrieval is a local deterministic BM25 implementation. Tokenization
uses Unicode normalization and preserves legal identifiers and terms such as
`7.1`, `12.3(a)`, `Section 73`, `INR`, and `30 days`; there is no aggressive
stop-word removal. The current implementation materializes the authorized
chunk set for each sparse query. This is appropriate for the Phase 5 boundary
and small fixtures, but its memory/latency cost must be measured before the
corpus grows substantially. A future PostgreSQL FTS or dedicated index should
be a measured decision, not a premature dependency.

## Hybrid ranking

Hybrid retrieval uses Reciprocal Rank Fusion, never an average of incompatible
dense and BM25 score scales:

`RRF(chunk) = sum(1 / (rrf_k + component_rank))`

The default `rrf_k` is 60. Component ranks/scores and the final score/rank are
returned for diagnostics and future evaluation. All ties use chunk ID.

## API and boundaries

`POST /api/v1/search` accepts `query`, an explicit `scope`, `top_k`, and
`mode` (`dense`, `sparse`, or `hybrid`). The response contains provenance from
Phase 4, ranking details, candidate counts, scope, and latency. It exposes no
ORM models. Reranking is optional and documented separately in
`reranking.md`; it does not replace dense retrieval, BM25, or RRF. There is no
chat endpoint, citation generation, observability backend, or answer
generation in this phase.

## Developer manual verification

The repository includes a developer-only CLI and synthetic fixture seeder. The
fixture is not a real contract and is not production knowledge. From the
project root on Windows:

```powershell
docker compose up -d
docker compose ps
docker compose exec api uv run alembic upgrade head
uv run python scripts/seed_retrieval_fixture.py
uv run python scripts/search.py "termination notice period" --tenant-id 9f61566b-d9fb-5bbd-99fd-23831653ce34
uv run python scripts/search.py "termination notice period" --tenant-id 9f61566b-d9fb-5bbd-99fd-23831653ce34 --mode dense
uv run python scripts/search.py "termination notice period" --tenant-id 9f61566b-d9fb-5bbd-99fd-23831653ce34 --mode sparse
uv run python scripts/search.py "termination notice period" --tenant-id 9f61566b-d9fb-5bbd-99fd-23831653ce34 --mode hybrid
```

Use the tenant ID printed by the seed command; it is deterministic only when
the default fixture tenant is used. The CLI supports `--top-k`,
`--document-id`, `--document-version-id`, and `--preview-length` (default 500).
It prints N/A for unavailable component fields and fails closed if
`--tenant-id` is omitted.

API example using the actual request schema:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/search `
  -H "Content-Type: application/json" `
  -d '{"query":"termination notice period","scope":{"tenant_id":"9f61566b-d9fb-5bbd-99fd-23831653ce34"},"mode":"hybrid","top_k":5}'

Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/search `
  -ContentType "application/json" `
  -Body '{"query":"termination notice period","scope":{"tenant_id":"9f61566b-d9fb-5bbd-99fd-23831653ce34"},"mode":"hybrid","top_k":5}'
```

For isolation checks, use the seeded tenant ID with the fixture document and
version IDs printed by the seeder, then repeat the CLI/API call with another
tenant ID or a different document/version ID. No fixture chunks should be
returned. Repeating the same query and scope should produce the same order.

Manual demonstration queries:

- `termination notice period` — termination should rank highly.
- `indemnification` — indemnification should rank highly.
- `limitation of liability` — liability should rank highly.
- `automatic renewal` — renewal should rank highly.
- `governing law India` — governing-law should rank highly.
- `thirty days prior written notice` — BM25 should strongly retrieve termination.
- `12.3(a)` — the identifier fixture should be retrieved.

## Evaluation and scaling boundary

Diagnostics capture the inputs needed for future Recall@K, Precision@K,
Hit@K, MRR, and nDCG evaluation, but no quality metric is claimed without a
labeled dataset. PostgreSQL/pgvector remains the system of record because it
already provides transactional chunk ownership, tenant/version predicates,
and the verified HNSW vector index. Elasticsearch/OpenSearch is intentionally
not introduced before measured scale or quality evidence requires it.

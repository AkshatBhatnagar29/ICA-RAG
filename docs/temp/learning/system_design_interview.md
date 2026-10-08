# ICIA system-design interview preparation

## Architecture

**Why hybrid retrieval?** Dense handles paraphrase; BM25 handles exact legal
identifiers, dates, names, and amounts. RRF avoids fragile score calibration.

**Why PostgreSQL + pgvector?** One transactional, tenant-filterable system of
record for metadata and vectors. A specialized vector DB may scale differently,
but creates another consistency boundary.

**Why rerank?** A cross-encoder improves ordering over a small candidate set;
it cannot recover missing evidence, so Candidate Recall@40 is measured first.

## Scaling

**One million contracts?** Partition/index by tenant and version, batch ingestion,
measure HNSW/DB capacity, move BM25 to PostgreSQL FTS or a dedicated index only
with evidence, and isolate model workers.

**1000 concurrent users?** Bound provider concurrency, queue indexing, separate
read/write DB capacity, cache safe metadata selectively, and avoid duplicating
CPU models across too many workers.

## Reliability

**Groq is down?** Typed provider failure becomes a safe error; no fabricated
answer. **Reranker fails?** Explicit failure when requested, not a false success.
**PostgreSQL fails?** readiness/transaction failure stops evidence. **Redis fails?**
Current product paths have no Redis data dependency beyond lifecycle/health.

## Security

**Cross-tenant retrieval?** Signed tenant plus SQL predicates before dense/BM25.
**Prompt injection?** Retrieved text is data; output is validated. **Fake E123?**
IDs must exist in selected authorized evidence, not merely have the right shape.
**Unsafe agent?** Typed allowlisted tools, no shell/SQL/filesystem/arbitrary HTTP,
plus timeouts, dependency and repetition limits.

## RAG/agent follow-ups

Distinguish retrieval failure, reranker failure, provider failure, malformed JSON,
and citation failure. Explain why a 447-item registry must not become a 447-item
prompt. Explain why an agent is useful only when typed tool choice adds value and
why global evidence budget must span multiple tools.

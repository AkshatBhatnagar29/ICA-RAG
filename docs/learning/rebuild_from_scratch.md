# Rebuild ICIA from scratch

1. FastAPI/Uvicorn skeleton: learn ASGI, routing, schemas, dependency injection.
2. PostgreSQL/SQLAlchemy/Alembic: learn entities, constraints, sessions, migrations.
3. Auth/RBAC/tenant scope: learn identity versus resource authorization.
4. Upload/storage/validation: learn content boundaries, checksums, safe paths.
5. PDF/DOCX processing: learn pages, blocks, OCR, bounded subprocesses.
6. Structural chunking: learn hierarchy, deterministic identity, provenance.
7. Embedding provider: learn tokenization, vectors, batching, model caching.
8. pgvector/HNSW: learn ANN search and filtered SQL.
9. BM25: learn lexical scoring and exact-match retrieval.
10. RRF: learn rank fusion and deterministic candidates.
11. Reranker: learn cross-encoder quality/cost tradeoff.
12. Context builder: learn evidence registry versus bounded prompt.
13. LLM provider: learn timeouts, retries, structured JSON, untrusted output.
14. Citation validation: learn provenance-backed grounding.
15. Contract extraction/risk rules: learn deterministic product intelligence.
16. Comparison: learn version-to-version derived snapshots.
17. Legal RAG: learn corpus/version/source separation.
18. Agent: learn typed bounded orchestration and tool security.
19. Evaluation: learn goldens, Recall@k, MRR, nDCG, latency.
20. Observability/security: learn metrics, request IDs, prompt/data boundaries.
21. Deployment: learn Docker, health checks, volumes, TLS, secrets.

At each step write one failing test before optimizing. Rebuild the narrow
contract first; add scale infrastructure only after measuring the bottleneck.

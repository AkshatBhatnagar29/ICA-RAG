# ICIA repository map

## Reading convention

This is a source-driven map. `SOURCE CONFIRMED` means visible in code or a
migration. `ARCHITECTURAL INTENT` means an architecture document describes it.
`NOT IMPLEMENTED` means the requested concept is absent from executable code.

## Runtime core

| Area | Files | Responsibility | Priority | Execution |
|---|---|---|---|---|
| startup/config | `app/main.py`, `app/core/config.py`, `app/core/exceptions.py`, `app/core/logging.py` | Settings, lifespan wiring, exception mapping, JSON logs | HIGH | startup/request |
| API | `app/api/router.py`, `app/api/v1/router.py`, `app/api/v1/endpoints/*.py` | REST, HTML, health, auth, agent, contract routes | HIGH | request |
| auth | `app/security/auth.py`, `app/models/auth.py`, `app/schemas/auth.py` | scrypt passwords, signed HS256 access tokens, roles, memberships | HIGH | request |
| DB | `app/db/base.py`, `app/db/session.py`, `app/db/repositories/*`, `app/models/*` | SQLAlchemy metadata, async sessions, repositories, entities | HIGH | startup/request |
| ingestion | `app/services/ingestion/*` | upload validation, storage, PDF/DOCX processing, OCR, provenance | HIGH | request/processing |
| chunk/index | `app/services/indexing/chunking.py`, `embeddings.py`, `service.py` | structural chunks, E5 vectors, pgvector rows | HIGH | indexing |
| retrieval | `app/services/retrieval/*` | query normalization, dense, BM25, RRF, scope filtering | HIGH | request |
| reranking | `app/services/reranking/*` | local FastEmbed ONNX cross-encoder | HIGH | request/evaluation |
| generation | `app/services/generation/*` | bounded context, Groq protocol, JSON parsing, citations | HIGH | request |
| contract intelligence | `app/services/contracts/*`, `app/models/contract_analysis.py` | extraction, evidence gates, deterministic risks, persistence | HIGH | request |
| comparison | `app/services/contracts/comparison*.py`, `app/models/contract_comparison.py` | version comparison, clause matching, derived snapshot | HIGH | request |
| legal RAG | `app/services/legal/*`, `app/models/legal.py` | versioned legal corpus ingestion/retrieval/evidence | HIGH | request/seed |
| agent | `app/services/agents/*` | typed planner, bounded tool execution, mixed synthesis | HIGH | request |
| evaluation | `app/services/evaluation/*`, `scripts/*evaluate*`, `reports/*` | retrieval, golden, reranker experiments | MEDIUM | evaluation |
| observability | `app/observability/*` | metrics, request IDs, telemetry, health | MEDIUM | startup/request |
| UI | `app/api/v1/endpoints/ui.py`, `templates/*` | server-rendered Jinja2 HTML/CSS | MEDIUM | request |

## Supporting and lower-priority files

`__init__.py` files are package markers. `app/schemas/*` are boundary contracts;
they do not perform persistence. `scripts/*seed*`, dataset adapters, and report
generators are operational/evaluation tooling. Cache directories, `__pycache__`,
`.pytest-*`, `.mypy_cache`, and generated model/data files are LOW priority.

## Import direction

Endpoints import services and schemas. Services import models, repositories,
providers, and domain schemas. Models import only SQLAlchemy/base types. The
retrieval service owns dense/BM25/fusion orchestration; generation owns context
and provider calls; agent synthesis composes contract and legal evidence.

## Important source-vs-documentation findings

- SOURCE CONFIRMED: PostgreSQL/pgvector is the vector store; there is no second
  vector database.
- SOURCE CONFIRMED: `ResourceManager` constructs Redis, but no application
  `get`, `set`, or Redis key operation exists. Redis is infrastructure/health
  support, not a current product cache or source of truth.
- SOURCE CONFIRMED: `OCRmyPDF` is not a dependency or Docker package. Tesseract
  and optional LibreOffice are used.
- SOURCE CONFIRMED: Jina is the runtime reranker default. MiniLM is used by
  controlled evaluation scripts/reports only.
- SOURCE CONFIRMED: no agent persistence or conversation table exists.
- SOURCE CONFIRMED: comparison is deterministic; it does not call the LLM.
- ARCHITECTURAL INTENT: some older architecture documents describe future
  phases; always prefer current code and migrations when they disagree.

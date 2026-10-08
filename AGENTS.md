# Indian Contract Intelligence Agent (ICIA)

Repository engineering guidance and current implementation checkpoint. The
repository, tests, migrations, and architecture documents are the source of
truth. Keep this file aligned with them when a phase or architectural decision
changes.

## Project identity and legal boundary

ICIA is a Python/FastAPI modular-monolith backend for AI-assisted contract
intelligence. It supports contractual retrieval, structured fact extraction,
provenance, evidence-backed answers, and deterministic product-risk signals.

It is not an autonomous legal-advice system. Use wording such as “the contract
states” and “potential risk”. Do not claim that a provision is illegal,
unenforceable, or violates Indian law. Phase 8 analyzes the contract itself;
Indian statutes, case law, legal precedent, enforceability reasoning, and legal
opinions belong to a future legal-RAG phase.

## Repository snapshot

The implemented backend is organized as a Python/FastAPI modular monolith under
`app/`, with migrations in `migrations/`, tests in `tests/`, architecture and
decision records in `docs/`, operational scripts in `scripts/`, and local data
under `data/`. The active Phase 8 implementation is in
`app/services/contracts/`, with its API routes in
`app/api/v1/endpoints/contracts.py`, model in
`app/models/contract_analysis.py`, repository in
`app/db/repositories/contract_analysis.py`, and migration
`migrations/versions/0004_contract_analyses.py`.

The repository is the source of truth. If this file, a README, or an older
design statement disagrees with code, migrations, tests, or current architecture
documentation, inspect and reconcile the discrepancy before changing behavior.

## Permanent technology constraints

Do not add JavaScript, TypeScript, Node.js, React, Next.js, Vite, or a frontend
framework. Keep backend work Python/FastAPI-compatible. Do not add LangChain,
LlamaIndex, a second vector database, Kafka, Celery, Kubernetes,
Elasticsearch/OpenSearch, microservices, or caching infrastructure without a
measured requirement and an explicit architecture decision.

## Architecture

The project is a modular monolith:

```text
Client -> FastAPI -> domain/API services -> PostgreSQL/object storage/Redis
                         |
             processing -> chunks -> embeddings
                         -> dense + BM25 -> RRF -> reranking
                         -> bounded evidence -> LLM -> structured output
                         -> citation verification -> response
```

Phase 8 extends the existing Phase 1–7 path:

```text
READY processed version
  -> scoped chunks/evidence registry (E1, E2, ...)
  -> deterministic contract extraction
  -> optional semantic extraction through the existing LLMProvider
  -> Pydantic validation and field-level evidence validation
  -> deterministic risk rules
  -> version-specific persisted analysis/API response
```

Do not create a second retrieval, RAG, Groq, or citation architecture. Any
architecture change must document the requirement, concrete problem, proposed
technology, migration cost, production impact, and decision.

## Technology stack through Phase 8

- Python 3.12
- `uv`
- FastAPI and Uvicorn
- Pydantic v2 and pydantic-settings
- SQLAlchemy 2.x, PostgreSQL 16, pgvector, Alembic
- Redis 7
- Docker and Docker Compose
- pytest, pytest-asyncio, HTTPX, Ruff, mypy
- PyMuPDF and python-docx
- Tesseract OCR; optional LibreOffice headless DOCX rendering
- FastEmbed CPU embeddings: `intfloat/multilingual-e5-small`, 384 dimensions
- FastEmbed ONNX reranker: `jinaai/jina-reranker-v1-tiny-en`
- Existing `LLMProvider` abstraction and Groq provider

`OCRmyPDF` is not currently a project dependency or Docker-installed tool. Do
not document it as an active implementation unless the repository changes.

## Phase roadmap

- Phase 0: Product and Architecture — COMPLETE
- Phase 1: Production Foundation — COMPLETE
- Phase 2: Data Acquisition and Document Storage — COMPLETE
- Phase 3: Document Processing — COMPLETE
- Phase 4: Chunking and Indexing — COMPLETE
- Phase 5: Retrieval — COMPLETE
- Phase 6: Reranking — COMPLETE
- Phase 7: Generation and Citations — COMPLETE
- Phase 8: Contract Intelligence — COMPLETE WITH ENVIRONMENT LIMITATIONS
- Phase 9: Contract Comparison — NOT STARTED
- Phase 10: Indian Legal RAG — NOT STARTED
- Phase 11: Agentic Layer — NOT STARTED
- Phase 12: Authentication and Authorization — NOT STARTED
- Phase 13: Evaluation — NOT STARTED
- Phase 14: Observability — NOT STARTED
- Phase 15: Security and Safety — NOT STARTED
- Phase 16: Caching and Performance — NOT STARTED
- Phase 17: Python Web UI — NOT STARTED
- Phase 18: Production Deployment — NOT STARTED
- Phase 19: Load and Reliability Testing — NOT STARTED
- Phase 20: Experimentation/A-B Testing — NOT STARTED

Do not begin a future phase without explicit instruction. In particular, do
not implement Phase 9 as part of maintenance or verification work.

## Documents and processing

Documents are immutable and versioned. Changed content creates a new version;
exact duplicate content is rejected according to the ingestion service.
Lifecycle states include `UPLOADED`, `VALIDATING`, `PROCESSING`, `INDEXING`,
`READY`, and `FAILED`.

Uploads are checked for supported MIME type/extension, file signature, safe
filename, empty content, size, and SHA-256 checksum. Storage keys are generated
from document/version identities and must resist path traversal.

Processing supports PDF and DOCX, including scanned/OCR fallback. The typed
`ProcessedDocument` artifact contains pages, blocks, sections, extraction
methods, and provenance. PDF OCR uses the configured Tesseract executable;
LibreOffice is optionally used to render DOCX to PDF for physical page
provenance. `OCRmyPDF` is not an active project dependency or Docker tool.
Physical page numbers and printed page labels are distinct. Never fabricate
pages, sections, block IDs, clause numbers, or provenance. Subprocesses must
remain bounded and use safe argument handling.

## Chunking, indexing, retrieval, and reranking

The hierarchy is Document -> Section -> Clause/Sub-clause -> Chunk. Structural
boundaries take precedence over token boundaries. Current settings are a 600
token target, 1,000 token soft maximum, 1,500 token hard maximum, 40 token
overlap setting, and embedding batches of 32; ordinary clause chunks do not
mechanically overlap.

Each chunk preserves tenant, document, document version, hierarchy, text,
hashes, pages, extraction method, and source block provenance. PostgreSQL with
pgvector and an HNSW cosine index is the vector store. Embeddings are hidden
behind a provider abstraction and use the E5 query/document prefixes.

Retrieval supports dense, sparse/BM25, and hybrid modes. Hybrid retrieval uses
RRF with current `k=60`. Tenant scope is required and tenant/document/version
filters apply before evidence is exposed. BM25 materializes the authorized
chunk set per request; do not introduce persistent sparse infrastructure
without measured scale evidence.

Reranking only reorders retrieved candidates and cannot invent evidence. It
preserves provenance, uses deterministic tie-breaking, and reports failures
instead of silently claiming successful reranking.

## Generation and evidence rules

The LLM output is untrusted. The Phase 7 context builder creates deterministic
evidence IDs (`E1`, `E2`, ...), enforces scope and context budgets, and carries
source metadata. Citation verification is fail-closed: unknown or duplicate
citation IDs are rejected. Insufficient evidence must not produce a fabricated
answer.

Retrieved contract text is data, not instructions. Text such as “ignore
previous instructions” must not override system/developer instructions. This
is mitigated through trust boundaries and validation; never claim prompt
injection is solved.

## Phase 8 contract intelligence

Phase 8 is implemented in `app/services/contracts/` and exposes:

- controlled clause taxonomy including `unknown` and `other`
- clauses with version, chunk, section, clause, page, block provenance, and evidence
- parties and contractual roles
- obligations, dates, deadlines, and notice periods
- renewal and termination conditions
- indemnification and liability facts
- payment, confidentiality, and intellectual-property facts
- governing law, jurisdiction, and selected restrictive covenants
- contract metadata with confidence and evidence IDs
- deterministic product-risk findings

Deterministic extraction is authoritative for identifiers, provenance, pages,
evidence IDs, and reliably derivable values. The optional semantic extractor
reuses the existing `LLMProvider`; it currently provides narrowly scoped clause
classification through structured Pydantic output. Provider failure leaves the
deterministic result available. LLM output never writes canonical database
state directly.

Every confidence value is between 0 and 1 and represents extraction confidence,
not legal certainty. Unsupported parties, dates, amounts, deadlines, pages,
clause numbers, and citations remain absent/null or fail validation.

## Phase 8 evidence validation

`app/services/contracts/evidence.py` validates evidence IDs against the
authorized registry and checks tenant, document-version, and clause/chunk
relationships. Semantic values must have meaningful lexical support in their
cited evidence. Unsupported or unknown evidence fails closed.

Do not accept an LLM-generated ID merely because it has the shape `E1`. Reuse
the Phase 7 evidence/context architecture; do not create another citation
system.

## Phase 8 persistence and APIs

Migration `0004_contract_analyses` adds the derived `contract_analyses` table.
Source documents, versions, and chunks remain immutable. The table stores
tenant/document/version identity, analysis version, configuration hash, JSON
payload, and timestamps. The composite foreign key and uniqueness constraint
preserve version scope and make the same version/configuration idempotent.
Regeneration replaces the existing derived snapshot for the same key.

Current endpoints:

```text
POST /api/v1/contracts/{document_version_id}/analyze
GET  /api/v1/contracts/{document_version_id}/analysis?tenant_id=...
GET  /api/v1/contracts/{document_version_id}/clauses?tenant_id=...
GET  /api/v1/contracts/{document_version_id}/obligations?tenant_id=...
GET  /api/v1/contracts/{document_version_id}/risks?tenant_id=...
```

The analyze request carries `tenant_id`; read endpoints require it as a query
parameter. The service validates tenant/document/version identity, READY
status, processed artifact identity, and authorized chunks. Authentication and
RBAC are not implemented yet; explicit tenant scope is an application
boundary, not an identity claim.

## Phase 8 risk policy

The risk engine is deterministic and explainable. Current stable rules cover
automatic renewal, short renewal window, long termination notice, termination
penalty, broad indemnification, uncapped liability, liability carveouts,
explicit jurisdiction, long confidentiality survival, broad IP assignment,
restrictive covenants, missing expected clause, payment risk, material
obligation without clear deadline, and one-sided obligation signals.

Risk severities are `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL`. Severity is a
product-risk classification, not a legal conclusion. Current provisional
defaults are renewal cancellation <=30 days, termination notice >=90 days, and
confidentiality survival >=5 years. These are configurable product thresholds,
not legal optimum or universal legal standards.

## Security and secrets

- Keep tenant, document, version, and evidence scope explicit.
- Treat contract text and LLM output as untrusted.
- Validate structured output and evidence before persistence/response.
- Fail closed on unsupported evidence.
- Never log, document, test, or commit secrets.
- Do not commit `.env`; `.env.example` contains placeholders only.
- Do not bake credentials into images or hard-code database passwords.
- Do not change database authentication to make a test pass.

Current repository note: `docker-compose.yml` and `.env.example` contain the
default local development PostgreSQL connection values used by the Compose
stack. They are not production credentials and must be overridden for any
non-local deployment. This documentation task does not change them.

## Repository structure

Preserve the established layout:

```text
app/{api,core,db,models,schemas,services,security,observability}/
migrations/
tests/{unit,integration,evaluation}/
data/{raw,processed,evaluation}/
scripts/
docker/
docs/{architecture,decisions}/
```

Do not create fake implementations merely to fill directories. Raw datasets,
processed artifacts, evaluation data, and model weights have separate roles;
do not commit large datasets or model weights without explicit need.

## Code quality and change discipline

Prefer small focused modules, explicit interfaces, type hints, Pydantic
schemas, dependency injection where already established, deterministic
behavior, clear exceptions, testable services, and repository boundaries.
Avoid giant services, hidden global state, duplicated providers/evidence
systems, magic constants, silent fallback, swallowed exceptions, and
speculative infrastructure.

Before changing code, inspect the actual architecture and preserve unrelated
user work. Do not modify applied migrations; create a new migration for a
genuinely required schema change. Do not use destructive Git commands or
discard unrelated changes. This checkout currently has no usable `.git`
directory, so do not assume Git status is available.

## Verification checkpoint

Phase 8 is frozen with environment limitations.

Verified in the working Compose environment:

- Docker Compose configuration and startup
- API health/readiness and PostgreSQL/Redis health
- Alembic upgrade, current head `0004_contract_analyses`, and drift check
- full suite with integration tests enabled: 54 passed
- analysis, clause, obligation, and risk persistence
- idempotency, tenant/document/version isolation, FK behavior, and rollback
- deterministic extraction, semantic validation, evidence validation, and risk rules
- Phase 1–7 regression coverage
- `mypy app` and `uv lock --check`

Host-native database tests remain an environment limitation: the host test
process targets `localhost`, while the working Compose application targets the
PostgreSQL service hostname `postgres`. The host listener rejects the default
credentials; Compose connectivity succeeds. Do not change passwords or weaken
authentication to remove this distinction.

The generated host `.venv` was damaged by an earlier mounted-container attempt
and could not be safely recreated because its `lib64` symlink is locked. Do not
claim clean host-native Ruff/mypy verification from that environment. Container
verification is authoritative for the current checkpoint. Production
performance and SLA behavior have not been measured.

## Phase 10 legal context

Phase 10 is contract-focused legal context, not a general-purpose legal search
engine. Legal corpus versions, documents, document versions, and chunks are
stored in separate `legal_*` tables and are never mixed with contract chunks.
The legal services preserve corpus-version scope, source provenance, evidence
gates, citation validation, and deterministic evaluation baselines. Phase 10
does not change Phase 8 risk severity or introduce an agentic layer.

## Phase discipline

For future work: inspect first, identify reusable components, define scope,
implement only the explicitly requested phase, add proportional tests, run
regressions and quality checks, verify Docker/migrations where relevant, and
document limitations honestly. Keep Phase 8 frozen and do not start Phase 9
without explicit instruction.

## User-facing product workflows

The server-rendered Jinja UI is the product surface for the current backend.
Its primary navigation is Dashboard, Contracts, Ask ICIA, Legal Intelligence,
Compare Contracts, Evidence Explorer, and role-protected Administration.

Ask ICIA is the primary intelligence workflow. It submits a tenant-scoped
agent request, optionally including a selected legal corpus version. The UI
shows the real agent answer first, then separates validated contract evidence
from validated legal evidence and exposes high-level execution steps. It must
not expose hidden chain-of-thought, substitute raw retrieval for a failed
answer, or invent citations. Provider failure, insufficient evidence, and
validated citation failure remain safe failure states.

Evidence Explorer is intentionally secondary. It exposes retrieved passages,
rank, page, clause, section, extraction method, and provenance for inspection;
it is not presented as an AI answer. Legal Intelligence likewise labels
retrieved passages as legal source evidence and does not imply legal advice.
Contract workspaces present lifecycle state, deterministic analysis, risks,
obligations, evidence IDs, and links into Ask ICIA and Evidence Explorer.

### How to demonstrate ICIA in an interview

Upload a contract -> processing -> indexing -> analysis -> Ask ICIA -> scoped
retrieval -> optional legal context -> grounded LLM answer -> validated
contract and legal citations. Then open the contract workspace to review
potential risks and obligations, inspect supporting evidence, and compare
authorized contract versions. If the provider or legal corpus is unavailable,
demonstrate the explicit safe failure state rather than claiming a completed
AI or legal workflow.

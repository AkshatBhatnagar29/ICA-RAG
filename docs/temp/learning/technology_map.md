# ICIA technology map

| Technology | Runtime role | Why ICIA uses it | Cost/failure boundary | Alternatives and reason not selected |
|---|---|---|---|---|
| Python 3.12 | application language | typed async backend and ML ecosystem | interpreter/runtime errors; CPU inference competes with requests | Go/Java would require rebuilding Python document/ML integrations |
| FastAPI/Uvicorn | HTTP and ASGI server | typed request models, async endpoints, low ceremony | validation/handler errors; worker lifecycle matters | Flask lacks native typed async ergonomics; Django is broader than this modular monolith |
| Pydantic v2/settings | boundary validation/config | rejects malformed uploads, requests, LLM output, settings | validation errors are deliberate fail-closed boundaries | dataclasses alone do not validate external data |
| SQLAlchemy 2 + psycopg | async DB access/ORM | explicit transactions and PostgreSQL integration | pool/database outages; commit/rollback required | raw SQL would duplicate mapping; Django ORM conflicts with chosen FastAPI stack |
| PostgreSQL 16 | durable metadata/chunk store | transactions, constraints, joins, tenant filters | disk/connection/index pressure | document DB would weaken relational integrity; separate DB was not measured necessary |
| pgvector | vector column/operators | keeps vectors beside authorized rows | vector index memory/build/search cost | Pinecone/Qdrant/Chroma add operational systems; decision ADR-002 favors one DB |
| HNSW | approximate cosine index | fast ANN search with configured `m=16`, `ef_construction=64` | build RAM and recall/latency tradeoff | exact scan is simpler but slower at scale |
| Redis 7 | deployed resource/health dependency | reserved for future bounded ephemeral infrastructure | current app does not read/write keys | database-backed durable data remains authoritative |
| PyMuPDF/fitz | PDF extraction/rendering | text, blocks, pages, OCR fallback input | malformed/encrypted PDFs, subprocess timeout | browser/PDF JS not appropriate for backend processing |
| python-docx | DOCX extraction | native paragraphs/tables | structural fidelity and page provenance are limited | LibreOffice is optional rendering support |
| Tesseract | OCR executable | local scanned-PDF fallback | process timeout/model quality | OCRmyPDF is not installed; cloud OCR adds cost/data movement |
| LibreOffice | optional DOCX-to-PDF rendering | physical page provenance | optional executable and bounded subprocess | direct DOCX only loses physical pages |
| FastEmbed/ONNX | local embedding/reranker backend | CPU-local, cached models, no provider call for retrieval | model load latency/RAM/CPU | hosted embeddings increase latency/cost/data exposure |
| multilingual-e5-small | 384D dense embeddings | multilingual semantic retrieval and manageable CPU footprint | model quality/model cache failures | larger E5/BERT/API models cost more or require service dependency |
| BM25 | lexical retrieval | exact clause IDs, amounts, dates, names | materializes authorized corpus per request; scales poorly | persistent FTS/search engine deferred until measured |
| RRF | dense/sparse fusion | rank-based, score-scale independent, deterministic | fusion weights and `k=60` are product choices | score normalization is more data-sensitive |
| Jina reranker | runtime cross-encoder | improves early rank on candidate set | CPU latency, model load, failure is explicit | MiniLM is experimental and latency matching remains unresolved |
| Groq/OpenAI-compatible API | final generation | provider abstraction plus fast hosted inference | timeout, rate limit, auth, 5xx, malformed JSON | local LLM not selected for current CPU/resource envelope |
| Alembic | schema migrations | ordered, reviewable DB evolution | migration drift/order errors | ad hoc schema changes are unsafe |
| Jinja2/HTML/CSS | UI | server-rendered Python-only product surface | template/runtime errors; no SPA state layer | React/Next/Vite/Node explicitly prohibited |
| Docker Compose/Nginx | local and preproduction deployment | reproducible PostgreSQL/Redis/API and optional TLS proxy | image/storage/network/secret operations | Kubernetes/Celery/Kafka are not justified by current scale |

## Interview focus

Be able to explain why the system uses one modular monolith, why lexical and
dense retrieval complement each other, why authorization occurs before evidence
construction, why reranking cannot create evidence, and why the LLM response is
untrusted output rather than application state.

"""Generate the source-grounded ICIA interview handbook PDF."""

from __future__ import annotations

from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "Indian_Contract_Intelligence_Interview_Deep_Dive.pdf"
HTML_OUTPUT = ROOT / "docs" / "Indian_Contract_Intelligence_Interview_Deep_Dive.html"


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{cell}</th>" for cell in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def diagram(title: str, steps: list[str]) -> str:
    boxes = "".join(f"<div class='box'>{step}</div><div class='arrow'>-&gt;</div>" for step in steps[:-1])
    boxes += f"<div class='box'>{steps[-1]}</div>"
    return f"<div class='diagram'><strong>{title}</strong><div class='flow'>{boxes}</div></div>"


def build_html() -> str:
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><style>
@page {{ size: A4; margin: 18mm 16mm 17mm 16mm; }}
body {{ font-family: sans-serif; color: #1d2733; font-size: 9.2pt; line-height: 1.42; }}
h1 {{ color: #123b52; font-size: 22pt; border-bottom: 2px solid #d47b3f; padding-bottom: 5px; page-break-before: always; }}
h2 {{ color: #185b68; font-size: 15pt; margin-top: 16px; }}
h3 {{ color: #a24f2a; font-size: 11.5pt; margin-top: 12px; }}
p {{ margin: 5px 0 8px; }} ul, ol {{ margin-top: 3px; }} li {{ margin: 2px 0; }}
.cover {{ page-break-after: always; padding-top: 75mm; text-align: center; }}
.cover h1 {{ page-break-before: avoid; border: 0; font-size: 31pt; }}
.cover .strap {{ color: #a24f2a; font-size: 15pt; }}
.meta {{ color: #52636f; margin-top: 35mm; }}
.toc {{ page-break-after: always; }} .toc h1 {{ page-break-before: avoid; }}
.toc li {{ margin: 5px 0; }}
.callout {{ background: #edf5f4; border-left: 4px solid #16818a; padding: 8px 10px; margin: 9px 0; }}
.tip {{ background: #fff4df; border-left: 4px solid #d47b3f; padding: 8px 10px; margin: 9px 0; }}
.warning {{ background: #fff0ed; border-left: 4px solid #a24f2a; padding: 8px 10px; margin: 9px 0; }}
.label {{ font-weight: bold; color: #185b68; text-transform: uppercase; font-size: 8pt; letter-spacing: .4px; }}
table {{ width: 100%; border-collapse: collapse; margin: 8px 0 12px; font-size: 8pt; }}
th {{ background: #123b52; color: white; text-align: left; }} th, td {{ border: 1px solid #cbd5da; padding: 4px 5px; vertical-align: top; }}
tr:nth-child(even) {{ background: #f5f8f8; }}
code {{ font-family: monospace; color: #143d54; }}
.diagram {{ border: 1px solid #9bb8bc; background: #f6fbfa; padding: 8px; margin: 10px 0; page-break-inside: avoid; }}
.flow {{ display: flex; align-items: center; gap: 5px; margin-top: 8px; flex-wrap: wrap; }}
.box {{ border: 1px solid #185b68; background: white; padding: 7px; text-align: center; flex: 1 1 105px; min-height: 28px; }}
.arrow {{ color: #a24f2a; font-size: 14pt; }}
.small {{ font-size: 8pt; color: #52636f; }}
.qa {{ border-top: 1px solid #d5dee1; padding-top: 6px; margin-top: 10px; page-break-inside: avoid; }}
.pagebreak {{ page-break-before: always; }}
</style></head><body>
<div class='cover'><div class='label'>Source-grounded interview handbook</div>
<h1>Indian Contract Intelligence Agent</h1>
<div class='strap'>Interview Preparation and Understanding Guide</div>
<p>Architecture, implementation, trade-offs, failure modes, and interview answers</p>
<p class='meta'>Prepared from the repository at the current implementation checkpoint<br>26 September 2026<br><br>Source of truth: executable code, migrations, tests, and current deployment files</p></div>

<div class='toc'><h1>Contents</h1><ol>
<li>Executive Overview</li><li>Problem, Requirements, and Scope</li><li>Architecture and Components</li><li>Technology Choices</li>
<li>Repository Map</li><li>End-to-End Workflows</li><li>Feature Deep Dives</li><li>Database and Data Model</li>
<li>API Deep Dive</li><li>Caching, Jobs, and State</li><li>Retrieval, RAG, LLM, and Agents</li><li>Concurrency and Transactions</li>
<li>Failure Handling</li><li>Security and Trust Boundaries</li><li>Performance</li><li>Scalability</li>
<li>Why We Built It This Way</li><li>What I Would Improve</li><li>Interview Question Bank</li><li>Model Interview Answers</li>
<li>Whiteboard Explanation</li><li>Explain It Without Code</li><li>One-Page Revision Sheet</li>
</ol><div class='callout'><b>Reading rule.</b> “Implemented” describes current runtime behavior. “Documented checkpoint” describes a recorded verification result, not a fresh run. “Improvement” is a recommendation, not an existing feature.</div></div>

<h1>1. Executive Overview</h1>
<h2>What the project is</h2>
<p><b>Indian Contract Intelligence Agent (ICIA)</b> is a Python 3.12/FastAPI modular monolith for tenant-scoped contract intelligence. It accepts PDF and DOCX contracts, preserves immutable document versions and provenance, indexes their contents, retrieves relevant evidence, produces evidence-backed answers, extracts structured contract facts, flags deterministic product-risk signals, compares analyzed versions, and can retrieve separately versioned legal-corpus evidence through a bounded agent.</p>
<p>The system is not an autonomous legal-advice system. It reports what a contract or authorized source states, exposes evidence, and labels risk as a product classification. It does not decide legality, validity, enforceability, or legal liability.</p>
<div class='callout'><b>30-second answer.</b> “I built a production-oriented contract intelligence backend. A user uploads a PDF or DOCX; the system validates and versions it, extracts structured text and provenance, creates hierarchy-aware chunks and 384-dimensional E5 embeddings, and stores them in PostgreSQL with pgvector. Search combines dense vectors with request-scoped BM25 and optional local reranking. Chat is fail-closed: the model receives bounded, tenant-authorized evidence and citations are verified by the application. Separate deterministic services extract clauses, obligations, and risk signals, compare contract versions, and support a bounded contract-plus-legal agent.”</div>
<div class='tip'><b>2-minute answer.</b> “The interesting engineering problem is not just calling an LLM. It is preserving trust from upload to answer. Upload validation checks type, signature, size, filename, checksum, and duplicate versions. Processing preserves page, section, clause, block, and extraction-method provenance. Every retrieval request is tenant-scoped before evidence is exposed. Dense retrieval uses pgvector; sparse retrieval preserves legal identifiers and numbers; hybrid search uses reciprocal-rank fusion; an optional cross-encoder reranks only retrieved candidates. Generation gets application-assigned E1-style evidence IDs, a context budget, structured JSON output, and fail-closed citation validation. Contract analysis is mostly deterministic and persists a replaceable derived snapshot keyed by version and configuration hash. Auth uses signed access tokens, scrypt password hashes, and tenant memberships. The main trade-off is a simple modular monolith with synchronous CPU-heavy processing: it is understandable and easy to operate, but needs queues, object storage, distributed metrics, and scaling work for larger traffic.”</div>
<div class='tip'><b>5-minute answer structure.</b> Start with the user problem, draw the upload-to-index path, then draw search-to-answer. Explain tenant scope and evidence as the safety boundaries. Add the immutable document/version model, chunks with provenance and vectors, derived analysis/comparison snapshots, and separate legal corpus tables. Close with the current deployment shape, synchronous processing bottleneck, and the next scaling step: durable jobs plus isolated model workers.</div>
<h2>Why it is technically interesting</h2><ul><li>It combines transactional data, immutable versioning, vector search, lexical search, reranking, structured extraction, and bounded agent orchestration.</li><li>It treats provenance, tenant isolation, and citation validation as application invariants rather than prompt instructions.</li><li>It deliberately keeps contract analysis deterministic where possible and isolates optional LLM semantics from canonical state.</li><li>It contains realistic operational constraints: local model memory, OCR subprocess bounds, synchronous work, configuration hashing, and incomplete production-scale measurement.</li></ul>

<h1>2. Problem, Requirements, and Scope</h1>
<h2>The problem</h2><p>Contracts are long, structurally irregular, versioned, and full of high-value details such as notice windows, renewal mechanics, liability caps, obligations, payment terms, and governing-law clauses. Keyword search misses paraphrases; a raw LLM call can hallucinate; a flat text dump loses page and clause provenance; and a multi-tenant product cannot trust caller-supplied tenant identifiers.</p>
<h2>Requirements derived from the implementation</h2>
{table(['Category','Must have in current system','Current boundary'],[
['Functional','Upload PDF/DOCX; immutable versions; parse/OCR; chunk/embed; dense/sparse/hybrid search; evidence-backed chat; analysis; comparison; legal retrieval; bounded agent; auth/RBAC; UI.','Conversation persistence, durable agent runs, and standalone legal JSON search are absent.'],
['Reliability','Validation, checksums, transactional indexing, explicit FAILED state, structured errors, fail-closed citations, deterministic risk rules.','Upload/processing work is synchronous; no queue-based recovery.'],
['Security','Signed tenant context, membership and roles, scrypt passwords, bounded subprocesses, path-safe storage, scope-filtered evidence, prompt-injection boundaries.','No MFA, SSO, refresh-token rotation, rate limiter, or general policy engine.'],
['Performance','pgvector HNSW, embedding reuse, candidate bounds, context limits, CPU model cache.','BM25 scans authorized chunks per request; reranking and OCR consume API CPU.'],
['Consistency','Database constraints, immutable source versions, configuration-hashed derived snapshots, tenant filters.','Local object storage and database updates are not a distributed transaction.'],
['Scalability','Containerized topology and separated domain services inside one process.','No worker queue, autoscaling plan, replicas, sharding, or durable metrics backend.']])}
<h2>Naive approach and why it fails</h2><p>A naive design stores uploaded text in one table and sends the entire contract to an LLM. It fails on context limits, latency, OCR and page provenance, access isolation, reproducibility, citation trust, duplicate uploads, and version comparison. ICIA answers these by separating immutable sources from derived artifacts, retrieving bounded evidence, validating structured output, and making scope explicit at every boundary.</p>
<h2>Scope language for an interview</h2><div class='warning'><b>Do not overclaim.</b> The repository provisions Redis but does not use Redis reads/writes for application caching. It has a legal corpus and legal retrieval, but legal data is separate and not automatically authoritative. The recorded 54-test checkpoint and Compose results are historical documentation; they are not a fresh verification performed for this PDF.</div>

<h1>3. Architecture and Components</h1>
{diagram('Runtime architecture', ['Browser / API client','FastAPI routes','Auth + validation','Domain services','PostgreSQL + pgvector','Local object storage'])}
<p>Optional paths attach to the domain services: FastEmbed embeddings and the local ONNX reranker run in-process; Groq is the external LLM provider; Tesseract and optional LibreOffice are bounded subprocesses; Redis is provisioned but outside current application semantics; Nginx terminates TLS in production.</p>
{table(['Component','Receives / produces','Why it exists'],[
['FastAPI + Jinja UI','HTTP and multipart requests / JSON or server-rendered pages','One deployable application boundary with typed request validation.'],
['Auth context','Bearer token, optional tenant header / user, tenant, membership, role','Makes signed tenant scope authoritative and centralizes permission checks.'],
['Ingestion','PDF/DOCX bytes / original object, DocumentVersion, ProcessedDocument','Separates validation, storage, parsing, and lifecycle state.'],
['Indexing','ProcessedDocument / hierarchical Chunk rows and vectors','Preserves structure and makes retrieval efficient.'],
['Retrieval','Query plus tenant/document filters / ranked evidence with diagnostics','Combines semantic and exact-match strengths.'],
['Generation','Authorized evidence / structured answer and verified citations','Uses the LLM as an untrusted component.'],
['Contract services','READY version and chunks / analysis, risks, comparisons','Keeps deterministic product logic out of prompts.'],
['Legal and agent services','Corpus-scoped query or typed task / legal evidence or bounded answer','Prevents contract and legal corpora from being mixed implicitly.'],
['PostgreSQL','Relational rows and vectors / durable state','One transactional system for metadata, chunks, auth, and vectors.'],
['Local storage','Generated safe storage keys / original and processed artifacts','Keeps large files out of relational rows in the current deployment.']])}
<h2>Request lifecycle</h2>{diagram('Typical protected request', ['Request ID middleware','Bearer authentication','Tenant membership','Pydantic validation','Service orchestration','DB / model / provider','Response or error envelope'])}
<p>Unexpected exceptions are logged with a category and become a generic 500 containing a request ID. Expected <code>ApplicationError</code> instances retain a status and stable error code.</p>

<h1>4. Technology Choices</h1>
{table(['Technology','Where used','Why selected','Alternative and trade-off'],[
['Python 3.12 + uv','Application and dependency management','Strong data/AI ecosystem, typing, and reproducible lockfile workflow.','Node or Java could serve APIs; Python makes local inference and document tooling direct, but CPU-bound work needs isolation.'],
['FastAPI + Pydantic v2','Routes, schemas, validation','Typed async HTTP boundary and explicit models with forbidden extra fields in key domains.','Django would provide more batteries; FastAPI keeps the modular service boundary lighter.'],
['PostgreSQL 16','Metadata, auth, chunks, snapshots, legal data','Transactions, constraints, joins, JSON, and mature operational model.','MongoDB would simplify documents but weaken relational integrity; a second vector DB would add operational and consistency cost.'],
['pgvector','Dense embeddings and HNSW cosine index','Keeps vector retrieval beside tenant/version filters and transactional metadata.','Dedicated vector DB may scale independently later, but adds synchronization and another failure surface.'],
['SQLAlchemy 2 + Alembic','ORM and migrations','Typed relational access and versioned schema evolution.','Raw SQL can be more direct; ORM conventions reduce repeated mapping but require query discipline.'],
['FastEmbed E5 small','384-dim CPU embeddings','Local, cacheable, multilingual retrieval with query/passage prefixes.','Hosted embeddings can improve quality but add cost, latency, and data egress.'],
['BM25 + RRF','Sparse and hybrid search','Exact identifiers and semantic paraphrases complement each other without a second search service.','Persistent inverted index would scale better than per-request materialization.'],
['FastEmbed ONNX cross-encoder','Optional reranking','Improves ordering after bounded candidate retrieval while staying local.','Remote reranking can use stronger models but increases latency and cost; measured reports show roughly 2.6-4.5s means on small experiments.'],
['Groq provider','Optional semantic classification and chat','Existing provider abstraction, structured JSON, bounded timeout/retries.','A local LLM reduces egress but raises memory/latency; any provider remains untrusted.'],
['Docker Compose + Nginx','Development and one-VM production topology','Repeatable PostgreSQL/Redis/API deployment and TLS proxy.','Kubernetes would improve orchestration at scale but is explicitly deferred.'],
['Redis 7','Provisioned service and client lifecycle','Prepared for ephemeral infrastructure.','It is not currently a cache or readiness dependency, so claiming cache behavior would be inaccurate.']])}

<h1>5. Repository Map</h1>
{table(['Path','Architectural role'],[
['app/main.py','Application lifespan, dependency construction, exception handlers, request middleware.'],
['app/api/v1/endpoints/','HTTP boundary: auth, documents, search, chat, agent, contracts, admin, health, UI.'],
['app/security/','Token verification, password hashing, current context, permission dependencies.'],
['app/services/ingestion/','Upload validation, local storage, PDF/DOCX parsing, OCR, processing lifecycle.'],
['app/services/indexing/','Structure-aware chunking, deterministic identities, embeddings, transactional indexing.'],
['app/services/retrieval/ and reranking/','Query normalization, dense search, BM25, RRF, optional cross-encoder.'],
['app/services/generation/','Context budget, provider calls, structured output, citation verification.'],
['app/services/contracts/','Schema, deterministic extraction, evidence checks, risks, comparison.'],
['app/services/legal/ and agents/','Separate corpus retrieval and bounded typed tool orchestration.'],
['app/models/ and migrations/','SQLAlchemy entities and Alembic schema history 0001 through 0008.'],
['templates/','Current server-rendered product UI; no Next.js frontend is implemented.'],
['tests/','Unit, integration, and evaluation coverage for behavior, persistence, retrieval, agents, UI, and metrics.'],
['docker-compose*.yml, Dockerfile, docker/nginx/','Local and one-VM production deployment, OCR/runtime dependencies, TLS proxy.'],
['docs/architecture, docs/decisions, docs/evaluation','Design rationale, operating guidance, and benchmark artifacts; some older phase text is stale.']])}
<div class='warning'><b>Documentation conflict to mention.</b> README and older architecture files still describe Next.js, future authentication, or earlier phase checkpoints. Current code has Jinja UI, auth/RBAC, comparison, legal retrieval, and agents. No .git directory is present in this checkout, so commit history could not be verified.</div>

<h1>6. End-to-End Workflows</h1>
<h2>Upload, processing, and indexing</h2>{diagram('POST /api/v1/documents', ['Multipart upload','Read max + 1 byte','Filename/MIME/signature/checksum','Immutable version + original','PDF/DOCX parse + OCR','Processed JSON artifact','Hierarchical chunks','E5 embeddings','Transactional chunk replace','READY response'])}
<ol><li>Authentication supplies the authoritative tenant; a body tenant ID is ignored.</li><li>The bounded read detects oversize uploads before expensive processing. Extension, MIME, magic bytes, filename safety, emptiness, and checksum are validated.</li><li>Storage keys are generated from IDs, not user paths. Same-title identical content is rejected by checksum uniqueness; changed content receives a new version.</li><li>PDF native blocks are preferred; low-text/image pages can use Tesseract within a timeout. DOCX uses python-docx; physical pages are not invented when conversion is unavailable.</li><li>Indexing preserves sections, clauses, pages, printed labels, extraction method, and source-block provenance. Embeddings are checked for finite values and dimension 384.</li><li>Failure marks the version FAILED; the indexing transaction rolls back partial chunk changes.</li></ol>
<h2>Search and chat</h2>{diagram('POST /api/v1/chat', ['Normalize query','Force tenant scope','Dense / sparse / hybrid candidates','RRF fusion','Optional rerank','Evidence registry E1...','Context budget','Groq JSON output','Citation validation','Answer or safe insufficiency'])}
<p>Search can return diagnostics even when generation is not safe. Chat requires explicit reranking, a usable reranker score, and authorized evidence; otherwise it returns an insufficient-evidence answer without calling the LLM. The model never supplies citation metadata: the server copies it from the authorized registry.</p>
<h2>Contract analysis and comparison</h2>{diagram('Analysis', ['READY version','Scoped chunks','E1... evidence','Deterministic extraction','Optional semantic clause labels','Evidence validation','Risk rules','Idempotent JSON snapshot'])}<p>Comparison requires two authorized READY, already analyzed versions. It is deterministic and does not call Groq. Both analysis and comparison are derived snapshots, while source versions remain immutable.</p>
<h2>Agent query</h2><p>The agent accepts typed plans and exposes only <code>contract_search</code>, <code>contract_analysis</code>, <code>contract_comparison</code>, and <code>legal_search</code>. It has bounded steps, dependency checks, duplicate-call and cycle detection, timeouts, and separate contract/legal evidence namespaces. It has no SQL, shell, filesystem, arbitrary HTTP, Redis, or code-execution tool.</p>

<h1>7. Feature Deep Dives</h1>
<h2>Document intelligence</h2><p><b>What/why:</b> turn messy source files into traceable structured artifacts. <b>Internal decision:</b> structural boundaries take precedence over token boundaries; headings, clause numbers, and provenance survive chunking. <b>Edge cases:</b> corrupt files, MIME/signature mismatch, empty files, OCR timeout, low-text pages, missing printed labels, duplicate checksum, and partial indexing. <b>Interview point:</b> “READY means processing and indexing completed, not merely that bytes were uploaded.”</p>
<h2>Retrieval</h2><p><b>What/why:</b> dense embeddings capture paraphrase; BM25 preserves exact legal numbers and identifiers; RRF avoids forcing incomparable score scales into one formula. Candidate size is bounded, tenant predicates are applied in SQL first, and tie-breaking is deterministic. <b>Trade-off:</b> BM25 materializes the authorized chunk set per request, which is simple and auditable but a likely scale bottleneck.</p>
<h2>Contract extraction and risk</h2><p><b>What/why:</b> stable facts and risk signals should not depend on an LLM response. Deterministic extraction is authoritative for identifiers and provenance; semantic classification is optional and narrowly scoped. Evidence IDs and confidence values are validated. Rules include automatic renewal, short cancellation windows (<=30 days), long termination notice (>=90 days), long confidentiality survival (>=5 years), uncapped liability, indemnity, payment, IP, restrictive covenant, missing clause, and deadline signals. These are product-risk findings, not legal conclusions.</p>
<h2>Legal retrieval</h2><p>Legal corpus versions, documents, versions, and chunks use separate tables and <code>L1</code>-style evidence. Corpus-version scope is mandatory. The separation prevents accidental mixing of contract text and legal source text and makes source release identity explicit.</p>
<h2>Server-rendered UI</h2><p>The current product surface is Jinja-rendered: dashboard, contract workspace, upload, search, Ask ICIA, comparison, legal upload, administration, login, signup, and logout. The README's “Next.js later phase” is not current behavior.</p>

<h1>8. Database and Data Model</h1>
{diagram('Core entity relationships', ['Tenant - User membership','Tenant - Documents','Document - Versions','Version - Chunks','Version - Analysis snapshot','Version pair - Comparison','Corpus version - Legal documents - Legal chunks'])}
{table(['Table','Important design','Interview explanation'],[
['tenants / users / tenant_memberships','Unique tenant identifier, unique email, unique tenant-user membership, ADMIN/REVIEWER/VIEWER role.','Many-to-many users/tenants is represented explicitly so membership and role are durable and queryable.'],
['documents / document_versions','Version number and checksum unique per document; storage key unique; lifecycle check constraint.','The source is immutable and changed content becomes a new version, enabling reproducibility and comparison.'],
['chunks','Tenant/version identity, hierarchy, text, provenance JSON, 384-vector, content/config hashes; composite FK prevents mismatched document/version.','Retrieval needs both searchable text/vector and trustworthy location metadata.'],
['contract_analyses','Tenant/version, analysis version, configuration hash, JSON payload; unique configuration key.','Derived state can be replaced or regenerated without mutating source documents.'],
['contract_comparisons','Source/target versions, status, configuration hash, JSON payload; unique tenant/pair/configuration.','Deterministic comparison is idempotent and tied to exact versions.'],
['legal_*','Corpus release, legal document/version, chunk and vector tables separate from contracts.','Corpus provenance and scope are first-class, not a mixed search index.']])}
<h2>Indexes and constraints</h2><p>PostgreSQL indexes cover tenant IDs, document/version lookups, version-section-clause filters, and HNSW cosine vectors. Uniqueness prevents duplicate versions, chunk identities, analysis configurations, comparisons, corpus releases, and memberships. Foreign keys cascade source deletion to derived rows; parent chunks use SET NULL. JSON stores provenance/metadata and derived payloads where fields evolve as a validated Pydantic contract rather than requiring a column for every extracted fact.</p>
<h2>Transactions and concurrency</h2><p>Indexing deletes/rebuilds a version's chunks transactionally; a failure rolls back and marks the version FAILED. Idempotency is database-backed through unique constraints and configuration hashes. A concurrent duplicate upload or analysis can still race before commit; the unique constraint is the final arbiter and the service must map that conflict. There is no distributed transaction joining local files, PostgreSQL, Groq, and model caches, so recovery is operationally important.</p>
<h2>Whiteboard questions</h2><p>At 10x traffic, inspect BM25 scans, vector index memory, connection pool limits, synchronous ingestion, and JSON snapshot size. At 100x, move processing and embedding to durable jobs, use object storage, separate model workers, aggregate metrics, and consider a dedicated sparse/vector system only after measurements justify the added consistency cost.</p>

<h1>9. API Deep Dive</h1>
{table(['Method','Endpoint','Purpose','Important errors / controls'],[
['GET','/api/v1/health','Process liveness.','No database or Redis dependency; returns request ID.'],
['GET','/api/v1/ready','Dependency readiness.','Current implementation checks PostgreSQL; 503 when unavailable.'],
['POST','/api/v1/auth/token','Issue bearer token from OAuth2 form.','401 invalid credentials; 403 no membership.'],
['POST','/api/v1/auth/bootstrap','Development/test tenant and first user.','Requires matching bootstrap header; unavailable outside dev/test.'],
['POST','/api/v1/documents','Validate, process, index upload.','422 invalid input; 409 duplicate; failed processing; synchronous latency.'],
['POST','/api/v1/search','Return retrieval results and diagnostics.','422 schema; 403 missing scope; 503 reranker failure.'],
['POST','/api/v1/chat','Generate evidence-backed answer.','503 not configured; 504 timeout; 502 malformed output/citations; 429 rate limit.'],
['POST','/api/v1/contracts/{version}/analyze','Create or replace analysis snapshot.','404 scope; 422 non-READY/artifact; evidence fails closed.'],
['GET','/api/v1/contracts/{version}/analysis|clauses|obligations|risks','Read derived intelligence.','Tenant and version authorization.'],
['POST/GET','/api/v1/contracts/compare[/{id}]','Create/read deterministic comparison.','Requires authorized analyzed versions; idempotent configuration.'],
['POST','/api/v1/agent/query','Run bounded typed multi-tool workflow.','Plan/tool validation, timeouts, dependency/cycle/duplicate checks.'],
['POST/PATCH','/api/v1/admin/...','Manage users, memberships, roles.','Admin permission; final admin cannot be removed/demoted.']])}
<p>All routes live under <code>/api/v1</code>. Expected errors have <code>error.code</code>, message, and request ID. Payload tenant IDs are not trusted; the signed token's tenant is authoritative.</p>

<h1>10. Caching, Jobs, and State</h1>
<h2>What actually exists</h2><ul><li>FastEmbed model files are cached locally in a mounted model-cache volume.</li><li>Embedding reuse is database-backed by content hash and embedding configuration hash.</li><li>SQLAlchemy uses connection pooling and <code>pool_pre_ping</code>.</li><li>Redis is created and managed in the resource layer and is provisioned by Compose, but no application cache key is read or written on the request path.</li><li>No Celery/RQ/Kafka worker, job table, conversation table, durable agent-run table, or distributed cache is implemented.</li></ul>
<div class='warning'><b>Interview correction.</b> Do not say “Redis caches retrieval.” The accurate answer is: “Redis is provisioned for future ephemeral infrastructure, but current application semantics do not depend on it; readiness intentionally checks PostgreSQL only.”</div>
<h2>Why this matters</h2><p>The absence of a queue means upload, OCR, parsing, chunking, embedding, and indexing occupy the HTTP request. This is understandable for an early modular monolith and simplifies consistency, but it increases timeout risk and makes horizontal scaling harder when model memory and CPU are involved.</p>

<h1>11. Retrieval, RAG, LLM, and Agents</h1>
{diagram('RAG pipeline', ['Authorized query','E5 query embedding','pgvector dense','BM25 sparse','RRF fusion','ONNX reranker','Scoped evidence registry','Bounded context','Groq structured JSON','Server citation verification'])}
<h2>Exact mechanics</h2><p>Documents use the E5 <code>passage:</code> prefix and queries use <code>query:</code>. Dense scoring is <code>1 - cosine distance</code>. BM25 uses <code>k1=1.2</code> and <code>b=0.75</code>, with normalization that preserves legal identifiers, numbers, hyphenated terms, and Devanagari. Hybrid scoring uses:</p><p><code>RRF(d) = sum(weight / (rrf_k + rank))</code>, with default <code>rrf_k=60</code> and equal weights. Ties use chunk UUIDs for deterministic output.</p>
<h2>Why retrieval is a safety boundary</h2><p>SQL predicates apply tenant/document/version scope before evidence is exposed. The context builder assigns deterministic E1, E2 IDs to the full authorized registry, then selects by item and estimated-token limits. Items excluded from selected context are not citation-authorized. Unknown or duplicate IDs fail; model-supplied metadata is ignored.</p>
<h2>LLM behavior</h2><p>Groq is called with temperature zero, JSON response format, 30-second default timeout, and up to two retries. Missing configuration, timeout, connection/5xx, rate limit, auth, malformed output, and invalid citation cases map to distinct application errors. No sufficient authorized reranked evidence means no LLM call.</p>
<h2>Agent architecture</h2>{diagram('Bounded agent control flow', ['Typed request','Validated plan','Dependency/cycle checks','Typed tool calls','Scoped contract/legal evidence','Synthesis','Validated AgentResponse'])}<p>The agent is orchestration, not unrestricted execution. It has no arbitrary code or network tools. The key trade-off is reduced flexibility in exchange for a smaller attack surface and predictable resource bounds. There is no durable conversational memory.</p>
<h2>Quality, cost, and risk</h2><p>Latency includes database retrieval, local embedding/reranking, network LLM time, and retries. CPU reranking reports are experimental and based on small datasets; they should not be presented as production SLA numbers. Hallucination risk is reduced by evidence gates, structured output, and citation validation, but retrieval incompleteness and corpus quality remain risks.</p>

<h1>12. Concurrency and Transactions</h1>
{table(['Situation','Current mechanism','Residual risk / answer'],[
['Duplicate upload','Checksum uniqueness per document plus service duplicate detection.','Concurrent requests may race; DB uniqueness protects final state and should be translated to 409.'],
['Repeated analysis','Unique version/analysis/configuration key and replacement repository behavior.','Derived snapshot is replaceable; source version stays immutable.'],
['Partial indexing','Transactional chunk replacement and FAILED lifecycle.','Original/processed files and DB state require recovery checks because storage is not transactional with DB.'],
['Concurrent reads/writes','PostgreSQL isolation and scoped queries; immutable versions reduce mutation conflicts.','Long synchronous processing still consumes connections and request slots.'],
['Provider retry','Bounded provider retries and typed error classes.','Retries can duplicate external work; generation is not persisted as a durable job.'],
['Multi-process scaling','Not yet established; local model caches and process-local metrics.','Multiple workers duplicate model memory and fragment metrics; production recommends one worker today.']])}
<p>The central consistency strategy is “immutable source plus replaceable derived state.” That is easier to reason about than mutating extracted facts in place and supports regeneration when configuration changes.</p>

<h1>13. Failure Handling</h1>
{table(['Failure','Detection','Handling','User impact / recovery'],[
['Invalid upload','Pydantic, filename/MIME/signature/size checks','Reject before processing; structured status','Client fixes input; no READY version.'],
['Duplicate content','Checksum lookup/unique constraint','DuplicateDocumentError / 409','Existing version remains authoritative.'],
['OCR or parser failure','Subprocess timeout/exception or invalid artifact','Mark FAILED; return processing error','Retry with corrected file/configuration; no fabricated provenance.'],
['Database unavailable','SQLAlchemy exception/readiness','503 readiness or generic categorized 500','Restart/dependency recovery; request ID supports diagnosis.'],
['Redis unavailable','Redis client/health path if touched','Current API semantics do not depend on Redis','Readiness is intentionally PostgreSQL-only.'],
['Reranker unavailable','Explicit RerankingError','503; do not claim successful reranking','Use non-generation search or restore model dependency.'],
['LLM timeout/rate limit/malformed JSON','Provider typed error mapping','504/429/502 response; no fabricated answer','Retry only within bounded policy or show safe failure.'],
['Unknown/duplicate citation','Citation verifier','Fail closed with 502','Do not show unsupported answer as grounded.'],
['Wrong tenant','Signed tenant and membership checks','401/403 or boundary 404','Do not reveal cross-tenant existence.'],
['Agent cycle/duplicate/dependency error','Planner/executor validation','Reject or controlled agent failure','No arbitrary tool execution.']])}
<p>Every expected error includes a request ID. Normal logs exclude contract/provider content; errors are categorized as database, Redis, ingestion, auth, citation, provider, or internal without exposing sensitive payloads.</p>

<h1>14. Security and Trust Boundaries</h1>
<h2>Implemented controls</h2><ul><li>HS256 signed access tokens include subject, tenant, issue/expiry, issuer, audience, and access-token type.</li><li>Passwords use salted <code>hashlib.scrypt</code>; production requires a JWT secret of at least 32 characters and disallows bootstrap configuration.</li><li>Authenticated context verifies active user, tenant, membership, and role. ADMIN, REVIEWER, and VIEWER permissions are explicit.</li><li>Caller tenant fields are overwritten by authenticated scope; optional <code>X-Tenant-ID</code> must match the signed claim.</li><li>Generated storage keys and path resolution resist traversal; uploads and subprocesses are bounded.</li><li>SQLAlchemy parameters and Pydantic validation reduce injection and malformed-input risks.</li><li>Retrieved contract text is data, not instructions; the agent exposes typed tools only; evidence/citation checks are application-owned.</li></ul>
<h2>Weaknesses to state clearly</h2><p>No MFA, SSO, refresh-token rotation, email verification, general policy engine, application rate limiter, centralized audit log, or dependency security program is established in the current implementation. Local storage is not object-store replicated. Prompt-injection defense is defense-in-depth, not a claim that malicious text is solved.</p>

<h1>15. Performance</h1>
{table(['Operation','Cost shape / bottleneck','Current mitigation'],[
['Upload and parse','O(file size) plus OCR subprocess work; synchronous request.','Size bounds, subprocess timeouts, native extraction before OCR.'],
['Chunking','O(processed text) with structural parsing.','Token targets 600, soft 1000, hard 1500; bounded artifacts.'],
['Embedding','O(number of chunks * model inference); CPU and memory.','Batch size 32, local cache, reuse by content/config hash.'],
['Dense retrieval','Approximate vector search plus filtered relational predicates.','HNSW cosine index and bounded candidate count.'],
['BM25','O(authorized chunks) per request in current implementation.','Candidate/top-k bounds; likely first scale bottleneck.'],
['Reranking','O(candidate count * cross-encoder inference).','Candidate cap 40, batch 8, max length 512, optional flag.'],
['LLM generation','Network latency plus token cost and retries.','Context 6000 estimated tokens, output 1200, timeout/retry bounds.'],
['Analysis/comparison','O(chunks/facts) deterministic; comparison aligns extracted structures.','Version-scoped inputs and persisted snapshots.']])}
<p>There are no trustworthy project-wide latency or SLA numbers in the current implementation. Dated reranker experiments are small and should be used as directional evidence only.</p>

<h1>16. Scalability</h1>
{table(['Scale','What likely breaks first','Reasonable next step'],[
['100 users','Synchronous upload/CPU contention and local model warm-up.','Keep one worker, prewarm models, measure request queues and DB pool use.'],
['10,000 users','BM25 scans, upload timeouts, model CPU, local storage, process-local metrics.','Durable job queue and worker pool; object storage; persistent sparse index; centralized metrics; rate limiting.'],
['1 million users','Single PostgreSQL/vector instance, tenant filtering, snapshot volume, provider cost, operational blast radius.','Read replicas/partitioning after measurements, independently scalable retrieval, sharded or dedicated vector/search systems if justified, autoscaling workers, service extraction only where boundaries earn it.']])}
<p><b>Current vs proposed:</b> current production topology is one Linux VM, one FastAPI worker, PostgreSQL/pgvector, Redis, and Nginx. Horizontal API replicas are not a free win because local model memory and process-local metrics are not coordinated. The first architectural change should be durable asynchronous processing, not prematurely splitting every service.</p>

<h1>17. Why We Built It This Way</h1>
{table(['Decision','Alternative','Reasoning and trade-off'],[
['Modular monolith','Microservices','Shared domain boundaries and one deployment reduce network and operational complexity while the product is still evolving. Service extraction becomes attractive when independent scaling or ownership is measured.'],
['PostgreSQL + pgvector','MongoDB plus vector DB','Relational integrity, tenant filters, metadata, and vectors stay together. A separate vector system may win at scale but creates sync and consistency work.'],
['Evidence-backed generation','Prompt-only citations','Application-owned evidence and metadata make citations verifiable. It constrains model flexibility and requires retrieval/context plumbing.'],
['Immutable versions + derived snapshots','Mutate one contract record','Reproducibility, comparison, and regeneration improve. Storage and cleanup are more involved.'],
['Deterministic extraction first','LLM writes canonical facts','Deterministic provenance and rules are auditable. Semantic coverage is weaker until optional classification is added.'],
['Separate legal corpus','Mix legal and contract chunks','Prevents scope confusion and preserves corpus release provenance. It requires duplicate schema/retrieval concepts.'],
['Explicit tenant context','Trust request tenant ID','Signed membership scope prevents cross-tenant access. It requires auth dependencies on every protected path.'],
['Local CPU models','Hosted embeddings/reranker','Avoids data egress and recurring inference API cost. CPU latency and memory become operational constraints.'],
['Synchronous first implementation','Queue and workers immediately','Simpler consistency and local development. It is the clearest scale limitation today.']])}

<h1>18. What I Would Improve</h1>
{table(['Current approach','Problem','Proposed improvement','Trade-off'],[
['Synchronous upload/process/index','Long requests and API CPU contention','Durable job table plus worker queue; return status URL','Eventual completion and more operational state.'],
['Per-request BM25 materialization','Scales with authorized corpus per query','Persistent tenant-aware inverted index or measured search service','Index maintenance and synchronization complexity.'],
['Local object storage','Single-node durability and limited sharing','S3-compatible versioned object storage','Credential, network, and lifecycle management.'],
['Process-local metrics','No fleet-wide visibility or alerts','Prometheus/OpenTelemetry backend and centralized logs','Operational cost and cardinality discipline.'],
['One worker recommendation','Limited throughput; model duplication if multiplied','Dedicated inference workers and API/worker scaling policy','Queue latency and deployment complexity.'],
['Custom HS256 token flow','No key rotation/federation/MFA','OIDC provider, short-lived tokens, refresh rotation, MFA','External identity dependency and migration effort.'],
['No application rate limiter','Provider and expensive endpoints can be abused','Tenant/user quotas and Redis-backed rate limits','Redis becomes a real availability dependency.'],
['Small evaluation corpora','Weak confidence in retrieval/reranking generalization','Independent, diverse contract benchmark with regression gates','Dataset curation and labeling cost.'],
['Underspecified production bootstrap','Deployment docs conflict with dev-only endpoint','Document a one-time operator provisioning path or migration job','More deployment surface, but removes unsafe ambiguity.']])}

<h1>19. Interview Question Bank</h1>
<h2>Basic</h2><ul><li>What problem does ICIA solve?</li><li>Walk me through a contract upload.</li><li>Why are document versions immutable?</li><li>What is the difference between search and chat?</li><li>What does READY mean?</li><li>Why is this a modular monolith?</li><li>What are the main PostgreSQL entities?</li><li>What is the current frontend?</li></ul>
<h2>Intermediate</h2><ul><li>How do PDF, DOCX, and OCR paths differ?</li><li>How does chunking preserve legal structure and provenance?</li><li>Why use both BM25 and embeddings?</li><li>Explain RRF and its <code>k=60</code> parameter.</li><li>What does reranking change and what can it never change?</li><li>How is an LLM citation verified?</li><li>How is tenant isolation enforced if a request includes another tenant ID?</li><li>Why persist analysis as JSON?</li><li>Why is comparison deterministic?</li><li>How are legal sources prevented from being mixed with contract sources?</li></ul>
<h2>Advanced</h2><ul><li>What happens if indexing fails after some chunks are inserted?</li><li>What race occurs when two identical uploads arrive together?</li><li>How would you scale BM25?</li><li>Why is a vector DB not separate yet?</li><li>What breaks when adding multiple API workers?</li><li>How would you design durable async processing?</li><li>How would you measure retrieval quality and reranker benefit?</li><li>What is the distributed transaction boundary between files, DB, models, and Groq?</li><li>How would you protect the agent from tool loops and prompt injection?</li><li>How would you rotate the custom JWT secret?</li></ul>
<h2>Failure, scale, and “why?” follow-ups</h2><ul><li>What if PostgreSQL is down? What if Redis is down?</li><li>What if Groq times out or returns malformed JSON?</li><li>What if the model cites E99 or cites E1 twice?</li><li>What if a DOCX has no physical page representation?</li><li>What if a user requests another tenant's version?</li><li>Why not just send the whole contract to the LLM?</li><li>Why not use Redis as the source of truth?</li><li>Why not use a microservice per domain?</li><li>What happens at 100x traffic?</li><li>Which current metric would you add first?</li></ul>
<h2>Resume-specific questions</h2><ul><li>You say “AI agent”; what tools can it actually call?</li><li>You say “legal intelligence”; does the system give legal advice?</li><li>You say “hybrid retrieval”; show the exact scoring and data boundaries.</li><li>You say “production-first”; what is not production-ready?</li><li>You say “Redis”; where is the cache path?</li><li>You say “authentication”; what prevents tenant spoofing?</li><li>You say “evaluation”; how representative are the datasets?</li></ul>

<h1>20. Model Interview Answers</h1>
<div class='qa'><b>Question:</b> Why not call an LLM with the whole contract?<br><b>Testing:</b> Retrieval, context limits, safety, and provenance.<br><b>Answer:</b> “Whole-document prompting is expensive, latency-heavy, and loses control over what supports an answer. I first retrieve authorized chunks, preserve their page and clause provenance, bound the context, and give the model application-assigned evidence IDs. The model proposes wording, but the server verifies citations and metadata. That does not eliminate hallucination, but it makes unsupported citations fail closed.”<br><b>Follow-up:</b> “What if retrieval misses the clause?”<br><b>Think:</b> Retrieval quality is a separate measurable failure mode; improve chunking, hybrid search, reranking, and evaluation rather than loosening citation rules.</div>
<div class='qa'><b>Question:</b> Why PostgreSQL plus pgvector?<br><b>Testing:</b> Storage trade-offs and system boundaries.<br><b>Answer:</b> “The system needs relational constraints for tenants, versions, memberships, and derived snapshots, but also vector similarity over chunks. pgvector lets us filter by tenant and version in the same database and keeps operational consistency simple. A dedicated vector system could be better at very high vector scale, but then embeddings and metadata need synchronization and another failure path. I would move only after measurements show PostgreSQL is the bottleneck.”<br><b>Follow-up:</b> “What is the current vector index?”<br><b>Think:</b> HNSW with cosine distance, 384 dimensions, and configured m/ef-construction.</div>
<div class='qa'><b>Question:</b> Is Redis the cache?<br><b>Testing:</b> Whether the candidate read the implementation.<br><b>Answer:</b> “No. Redis is provisioned and its client lifecycle exists, but the current request path does not read or write application cache keys. Model caching is local filesystem caching, and embedding reuse is database-backed. That is an important distinction. Redis can support future rate limits or ephemeral jobs, but readiness deliberately checks PostgreSQL only today.”</div>
<div class='qa'><b>Question:</b> How do you prevent cross-tenant data exposure?<br><b>Testing:</b> Auth and data-access boundaries.<br><b>Answer:</b> “The signed token contains the tenant, and the request context verifies user activity and membership. Route payload tenant IDs are overwritten or ignored. Retrieval applies tenant predicates before evidence is built, and contract/legal services validate version ownership and scope. An optional tenant header must match the signed claim. The remaining improvement would be stronger centralized policy/audit controls and broader negative integration tests.”</div>
<div class='qa'><b>Question:</b> What is the first change for 100x traffic?<br><b>Testing:</b> Prioritization under constraints.<br><b>Answer:</b> “I would measure first, but the obvious pressure point is synchronous ingestion: OCR, parsing, embeddings, and indexing occupy the API process. I would add a durable job state machine and worker pool, move originals to replicated object storage, and make the API return processing status. In parallel I would replace per-request BM25 materialization with a persistent index. I would not start with microservices or sharding without measurements.”</div>

<h1>21. Whiteboard Explanation</h1>
<h2>What to draw</h2><ol><li>Draw <b>User/UI</b> and <b>FastAPI</b>.</li><li>Split FastAPI into <b>Auth/validation</b>, <b>ingestion/indexing</b>, <b>retrieval/generation</b>, and <b>contract/legal/agent services</b>.</li><li>Draw PostgreSQL with relational tables plus pgvector, and local object storage beside it.</li><li>Draw external Groq, local E5/reranker, Tesseract/LibreOffice, and Nginx only where relevant.</li><li>Add the two main arrows: upload to READY, and query to verified answer.</li></ol>
{diagram('Five-minute board', ['User/UI','FastAPI + auth','Ingestion -> READY','Postgres/pgvector + storage','Hybrid retrieval + rerank','Evidence IDs + bounded LLM','Verified answer'])}
<p>Say: “The core invariant is that every answer is bounded by authorized evidence. The core data invariant is that source versions are immutable and analyses are derived snapshots. The core scale limitation is synchronous CPU-heavy processing and per-request sparse retrieval.” Then mention tenant membership, separate legal corpus tables, and deterministic comparison.</p>

<h1>22. Explain It Without Code</h1>
<h2>Mental model</h2><ul><li><b>Components:</b> HTTP/UI, auth, ingestion, processing, indexing, retrieval, generation, contract intelligence, legal corpus, bounded agent, database, storage, models, provider.</li><li><b>Data:</b> immutable document versions; processed artifacts; hierarchy-aware chunks; vectors; evidence registries; JSON analysis/comparison snapshots; memberships; legal release versions.</li><li><b>Flows:</b> upload -> READY; search -> ranked passages; chat -> bounded context -> verified citations; analysis -> deterministic facts/risk; compare -> deterministic version delta.</li><li><b>Decisions:</b> modular monolith, PostgreSQL/pgvector, hybrid retrieval, application-owned citations, deterministic extraction, explicit tenant scope.</li><li><b>Failure points:</b> invalid files, OCR, DB, reranker, provider, citation validation, cross-tenant scope, synchronous timeouts.</li></ul>
<h2>Can I explain this project?</h2><ul><li>Can I state the 30-second version without saying “the LLM understands contracts”?</li><li>Can I draw the upload and chat paths?</li><li>Can I explain why a chunk has both text and provenance?</li><li>Can I explain dense, sparse, RRF, and reranking in order?</li><li>Can I state the exact citation fail-closed rule?</li><li>Can I distinguish Redis provisioning from caching?</li><li>Can I name the core tables and immutable/derived boundary?</li><li>Can I name the current bottleneck and first scale change?</li><li>Can I say what is not implemented?</li><li>Can I explain why the system is not legal advice?</li></ul>

<h1>23. One-Page Revision Sheet</h1>
<h2>ICIA in one page</h2><p><b>Purpose:</b> tenant-scoped, evidence-backed contract intelligence for PDF/DOCX documents, with separate legal retrieval.</p><p><b>Architecture:</b> Browser/API -> FastAPI -> auth/validation -> modular services -> PostgreSQL/pgvector + local storage; local E5/reranker; optional Groq; Tesseract/LibreOffice; Redis provisioned but not application cache; Nginx in production.</p><p><b>Key APIs:</b> health, ready, auth token/bootstrap, documents, search, chat, agent/query, contract analyze/read, compare/read, admin, Jinja UI.</p><p><b>Core flow:</b> validate -> version -> parse/OCR -> processed artifact -> structural chunks -> 384-dim E5 embeddings -> HNSW; query -> dense/BM25 -> RRF -> optional rerank -> E1 evidence -> bounded Groq JSON -> citation verification.</p><p><b>Database:</b> tenants/users/memberships; documents/versions; chunks; contract analyses/comparisons; separate legal corpus/document/version/chunks. Immutable source, replaceable derived snapshots, configuration-hash idempotency.</p><p><b>Numbers:</b> 25 MB default upload; chunks target 600, soft 1000, hard 1500 tokens; embedding dimension 384; RRF k 60; reranker candidates 40, default final 5; generation context 6000 estimated tokens; output 1200; Groq timeout 30s, retries 2; risk defaults 30/90/5 days/years.</p><p><b>Main trade-offs:</b> modular monolith is simple but less independently scalable; pgvector is operationally unified but may need separation at scale; local models avoid egress but consume CPU; deterministic extraction is auditable but semantically incomplete; synchronous processing is simple but blocks API capacity.</p><p><b>Top questions:</b> Why hybrid search? Why evidence IDs? Why PostgreSQL/pgvector? Why immutable versions? What if Groq fails? What if citation is invalid? How is tenant scope enforced? Why is Redis not a cache? What breaks at 100x? What would you improve first?</p>
<div class='callout'><b>Final interview sentence.</b> “The project’s central engineering idea is to make an LLM useful without making it authoritative: preserve source provenance, retrieve only authorized evidence, validate structured output, and keep deterministic business facts and risk rules outside the model.”</div>
<p class='small'>Accuracy note: this handbook was generated from the current checkout's code, migrations, tests, configuration, deployment files, and documentation. No git metadata was available. Historical evaluation numbers are labeled as experiments, not guarantees. Older contradictory docs are called out rather than silently merged into current behavior.</p>
</body></html>"""


def main() -> None:
    html = build_html()
    HTML_OUTPUT.write_text(html, encoding="utf-8")
    story = fitz.Story(html=html)
    temporary_output = OUTPUT.with_suffix(".tmp.pdf")
    writer = fitz.DocumentWriter(str(temporary_output))
    rect = fitz.paper_rect("a4")
    margin = 45
    mediabox = fitz.Rect(0, 0, rect.width, rect.height)
    content = fitz.Rect(margin, margin, rect.width - margin, rect.height - 42)
    while True:
        device = writer.begin_page(mediabox)
        more = story.place(content)
        story.draw(device)
        writer.end_page()
        if more[0] == 0:
            break
    writer.close()
    del writer
    document = fitz.open(str(temporary_output))
    document.set_metadata({"title": "Indian Contract Intelligence Agent - Interview Deep Dive", "author": "Generated from repository source"})
    for page_number, page in enumerate(document, start=1):
        page.insert_text((margin, rect.height - 22), f"ICIA Interview Deep Dive  |  {page_number} / {len(document)}", fontsize=7, color=(0.32, 0.39, 0.43))
    del page
    document.save(str(OUTPUT))
    document.close()
    temporary_output.unlink(missing_ok=True)
    print(f"Wrote {OUTPUT}")
    print(f"Wrote {HTML_OUTPUT}")


if __name__ == "__main__":
    main()
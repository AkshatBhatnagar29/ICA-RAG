# Request lifecycle

## Shared front door

`app/main.py:app` installs `RequestIdMiddleware`, includes the v1 router, and
creates providers in `lifespan`. Protected endpoints use `Depends` chains from
`app/security/auth.py`: `_claims` verifies the signed HS256 token, then
`get_current_context` loads `User`, `Tenant`, and `TenantMembership`;
`require_permission` checks the role. The signed tenant is authoritative before
any retrieval query is built.

## A: normal contract question

`POST /api/v1/chat` -> `chat()` -> `ChatRequest` -> `GenerationService.answer()`
-> `RetrievalService.search()` -> query normalization/scope validation ->
PostgreSQL pgvector dense query plus authorized-set BM25 -> `fusion.py` RRF ->
optional `LocalCrossEncoderReranker` -> `build_evidence_packet()` -> bounded
prompt -> `GroqProvider.generate()` -> `GeneratedAnswer.model_validate()` ->
`verify_citations()` -> `ChatResponse`.

Input is query/document scope. Output is answer and authoritative citation
metadata. Side effects are metrics and provider/model-cache activity. Errors are
scope failure, reranker failure, provider failure, malformed JSON, or citation
failure. The context builder now separates the full registry from selected
generation evidence (`GENERATION_TOP_K`, default 10; text budget 6000 tokens).

## B: legal question

The browser/API agent path is `POST /api/v1/agent/query` or UI `POST /ask`.
`route_task()` and `build_plan()` select `legal_search`; `LegalRetrievalService`
queries only `legal_*` tables and returns `LegalEvidence`. `assess_evidence`
gates insufficient results. Mixed synthesis preserves `E*` contract and `L*`
legal namespaces; `verify_legal_citations` checks provenance and selected IDs.
This is legal context, not legal advice or enforceability reasoning.

## C: multi-tool agent

`AgentService.run()` -> `build_plan()` -> `AgentExecutor.execute()` ->
`ToolRegistry` typed handlers (`contract_search`, `contract_analysis`,
`contract_comparison`, `legal_search`) -> state evidence -> bounded
`agents.synthesis.synthesize()` -> provider -> Pydantic -> contract/legal
validators. The executor enforces max steps/tool calls, dependencies, cycle
detection, duplicate-call detection, timeout, and tenant-scoped tools. It never
offers shell, SQL, Python, filesystem, or arbitrary HTTP tools.

## D: PDF upload

`POST /api/v1/documents` -> `create_document()` reads at most configured size
plus one byte -> `upload_document()` validates metadata, filename, MIME/signature,
checksum and creates immutable document/version/storage rows ->
`DocumentProcessingPipeline.process()` parses/normalizes/structures PDF and OCR
fallback -> stores `ProcessedDocument` -> `IndexingService.index_processed()`
chunks, embeds, writes pgvector chunks, and marks version `READY`. Failure rolls
back and records `FAILED`; subprocesses are bounded.

## E: comparison

`POST /api/v1/contracts/compare` -> auth permission ->
`ContractComparisonService.compare()` validates both authorized READY versions,
loads their analyses/chunks, applies deterministic clause matching/diff/risk
logic, validates evidence, persists `contract_comparisons`, and serializes
`ContractComparison`. It does not call Groq.

## F: insufficient evidence

Retrieval or legal evidence gates return a controlled result before generation.
Normal generation returns an insufficient-evidence answer with empty citations;
agent state becomes `INSUFFICIENT_EVIDENCE`. It does not dump the registry to
compensate for weak retrieval. Provider errors and citation failures are
separate failure categories.

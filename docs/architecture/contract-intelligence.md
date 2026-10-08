# Contract Intelligence (Phase 8)

Phase 8 analyzes one already-processed, versioned contract. It does not perform
Indian statute or case-law retrieval, enforceability analysis, legal opinions,
comparison, or autonomous legal advice.

## Data flow

`DocumentVersion READY` -> processed JSON and authorized `Chunk` rows ->
deterministic evidence registry (`E1`, `E2`, ...) -> typed extraction ->
Pydantic validation -> evidence-backed deterministic risk rules -> one derived
analysis snapshot.

Chunk IDs, pages, sections, clause numbers, and source blocks come only from
the processed artifact/indexed chunks. Contract text is data, not instructions;
the existing generation trust boundary remains in force. The current Phase 8
extractor is deterministic. An LLM extractor can be injected later behind the
same typed/evidence validation boundary, but untrusted model output is never a
canonical fact by itself.

## Schemas and taxonomy

`app.services.contracts.schemas` contains controlled clause types for
definitions, scope, services, deliverables, payment, fees, taxes, term,
renewal, termination variants, notice, indemnification, liability,
confidentiality, IP, data protection, warranties, insurance, audit,
compliance, governing law, jurisdiction, dispute resolution, assignment,
subcontracting, force majeure, non-compete, non-solicit, miscellaneous,
unknown, and other. Every extracted object carries confidence in `[0, 1]` and
evidence IDs. Unsupported values remain null.

## Risk engine

`risks.py` evaluates extracted facts with stable rule IDs. It currently covers
automatic renewal, short renewal notice, long termination notice, termination
penalties, uncapped liability, liability carveouts, long confidentiality
survival, and restrictive covenants. Findings are product-risk classifications,
not legal conclusions, and are emitted only with evidence IDs.

Default product thresholds are: renewal cancellation window <= 30 days,
termination notice >= 90 days, and confidentiality survival >= 5 years. These
are configurable policy defaults, not universal legal standards.

## Persistence and idempotency

`contract_analyses` stores the validated JSON snapshot with explicit tenant,
document, and version identity. `(document_version_id, analysis_version,
configuration_hash)` is unique. Re-analysis with the same configuration
replaces the derived snapshot; source documents/chunks are immutable.

## API

All routes require an explicit `tenant_id` and scope to the requested version:

* `POST /api/v1/contracts/{document_version_id}/analyze`
* `GET /api/v1/contracts/{document_version_id}/analysis?tenant_id=...`
* `GET /api/v1/contracts/{document_version_id}/clauses?tenant_id=...`
* `GET /api/v1/contracts/{document_version_id}/obligations?tenant_id=...`
* `GET /api/v1/contracts/{document_version_id}/risks?tenant_id=...`

The application has no authentication/RBAC implementation yet; tenant scope is
therefore an explicit application boundary, not an identity claim.

## Failure modes and limitations

Missing versions, tenant mismatch, non-ready versions, missing/mismatched
processed artifacts, malformed evidence, and unsupported facts fail closed or
remain null. The deterministic extractor is intentionally conservative and
does not replace legal review. Physical pages may be unavailable for an
unrendered DOCX, and complex semantics may require a future validated LLM
extractor. CPU work is text parsing; database work is scoped chunk loading and
snapshot persistence; no asynchronous worker or new vector store is needed in
this phase.

Field-level evidence validation rejects unknown IDs, mismatched versions,
tenants, chunks, and unsupported semantic values. A provider-independent
semantic extractor reuses the Phase 7 `LLMProvider` for narrowly scoped clause
classification. Its Pydantic output is checked against the evidence registry;
provider failures are logged and deterministic facts remain authoritative.

## Rule catalog

| ID | Condition | Default severity |
| --- | --- | --- |
| RULE-RENEWAL-001 | automatic renewal extracted | MEDIUM |
| RULE-RENEWAL-002 | cancellation notice <= 30 days | MEDIUM |
| RULE-TERMINATION-001 | termination notice >= 90 days | MEDIUM |
| RULE-TERMINATION-002 | termination penalty language | HIGH |
| RULE-INDEMNIFICATION-001 | covered indemnity claims extracted | MEDIUM |
| RULE-LIABILITY-001 | uncapped liability language | HIGH |
| RULE-LIABILITY-002 | liability carveout language | MEDIUM |
| RULE-JURISDICTION-001 | explicit jurisdiction/court | LOW |
| RULE-CONFIDENTIALITY-001 | survival >= 5 years | MEDIUM |
| RULE-IP-001 | IP assignment language | MEDIUM |
| RULE-RESTRICTIVE-001 | non-compete/non-solicit extracted | MEDIUM |
| RULE-CLAUSE-001 | no payment clause identified | LOW |
| RULE-PAYMENT-001 | payment found without deadline | MEDIUM |
| RULE-OBLIGATION-001 | obligation without clear deadline | LOW |
| RULE-OBLIGATION-002 | obligations plus one identified party | LOW |

Every rule is deterministic, evidence-backed, and a product-risk
classification—not a legal conclusion. Thresholds are configurable product
policy decisions, not universal legal standards.

## Status

Implemented: schemas, deterministic extraction, optional semantic seam,
evidence validation, risk rules, API, persistence, fixture, and tests.
Provisional: complex natural-language extraction and default risk thresholds.
Not implemented: legal reasoning, comparison, authentication/RBAC, full
observability, caching, frontend, and deployment work.

Tests use synthetic processed chunks and fake providers; live Groq calls are not
required for Phase 8 correctness. Database and Docker verification depends on
available local services.

# Contract intelligence

`ContractAnalysisService` validates tenant/version identity, READY status,
processed artifact identity, and authorized chunks before extraction. The
deterministic extractor creates typed `ContractIntelligence` facts: controlled
clause taxonomy, parties/roles, obligations, dates/deadlines, renewal and
termination, indemnity/liability, payment, confidentiality, IP, governing law,
jurisdiction, and selected restrictive covenants.

`contracts/evidence.py` validates evidence IDs against the authorized chunk
registry and checks tenant/version/chunk relationships plus meaningful lexical
support for semantic values. Optional `semantic.py` reuses the existing LLM
provider for narrowly scoped classification; failure leaves deterministic output.

`risks.py` is deterministic and explainable. Rules cover automatic renewal,
short renewal cancellation, long termination notice, termination penalty, broad
indemnity, uncapped liability, carveouts, explicit jurisdiction, long
confidentiality survival, broad IP assignment, restrictive covenants, missing
expected clause, payment risk, material obligation without a clear deadline,
and one-sided obligations. Each produces LOW/MEDIUM/HIGH/CRITICAL product-risk
findings with evidence IDs. These are potential product risks, not conclusions
about legality or enforceability.

Persistence is a derived `contract_analyses` snapshot keyed by tenant,
document/version, analysis version, and configuration hash. Source documents,
versions, and chunks remain immutable. API routes are in
`app/api/v1/endpoints/contracts.py`.

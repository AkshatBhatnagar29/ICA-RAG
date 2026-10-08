# Phase 9: Contract comparison

Contract comparison answers what changed between two immutable, processed
contract versions. It is a derived capability layered on Phase 8: the existing
validated `ContractIntelligence` snapshots provide clauses, structured facts,
provenance, and evidence IDs. Source documents and versions are never changed.

## Pipeline

The synchronous comparison service validates that both versions are READY,
belong to the requested tenant, and have completed Phase 8 analyses. It aligns
clauses using exact clause number, title, controlled taxonomy, and cautious
structural fallback. Unmatched clauses are represented as added or removed;
low-confidence matches remain explicitly `UNCERTAIN`.

Text is normalized only for whitespace and page-break artifacts. Numbers,
dates, names, currency, identifiers, and negation are preserved. Meaningful
aligned text changes retain both texts and deterministic word-level changed
spans.

Termination, renewal, liability, payment, and confidentiality facts are
compared from Phase 8 fields first. Summary counts and ordering are fully
deterministic. Text-only findings are not automatically legal conclusions.

An optional `SemanticComparisonResult` is available for an existing LLM
provider when wording requires interpretation. Its Pydantic schema and evidence
scope are validated; the model cannot introduce IDs or facts. The current
baseline implementation does not require a live LLM to produce a comparison.

## Evidence and impact

Every added, removed, or modified finding carries evidence from the relevant
target, source, or both. Validation checks that IDs belong to the aligned
clause and therefore to the correct tenant/version snapshot. Potential impact
language is product-risk wording only, such as a changed liability exposure or
termination window; it does not assess legality or enforceability.

## Persistence and security

`contract_comparisons` stores a JSON derived snapshot keyed by tenant, source
version, target version, comparison version, and configuration hash. Re-running
the same comparison is idempotent and uses the existing replacement semantics
for derived snapshots. Read and write APIs require explicit tenant scope.
Contract content remains untrusted data and never becomes an instruction to the
system or to an LLM.

## Limitations

Comparison depends on completed Phase 8 analyses and cannot recover facts that
were not extracted there. Semantic interpretation is optional and probabilistic.
The system compares contractual text and extracted facts; it does not compare
Indian statutes, case law, enforceability, or legal advice. Production latency
and SLA behavior have not been benchmarked.

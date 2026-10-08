# Phase 10: Contract-focused legal context

Phase 10 retrieves Indian legal evidence relevant to a contractual issue. It
is not a general legal search engine and does not provide legal advice or
enforceability conclusions.

## Boundaries

Contract chunks and legal chunks are separate PostgreSQL tables and namespaces:

```text
contract version -> contract retrieval -> contract evidence
legal corpus version -> legal retrieval -> legal evidence
                                      \- both -> evidence-backed legal context
```

Legal retrieval uses the existing dense embedding provider, per-request BM25,
RRF, and optional existing reranker. It does not assign unsupported authority
weights. `source_type`, citation, publisher, URI, and corpus release are
preserved as source metadata.

Legal documents retain section, subsection, article, paragraph, page, and
source provenance. A legal result is traceable through corpus version,
document version, and chunk. The corpus release is supplied explicitly in every
legal query; the service never silently searches all releases.

## Query and evidence safety

`build_deterministic_query` derives stable terms from the issue and validated
Phase 8 contract facts. Optional semantic expansion is additive and cannot
replace the deterministic query. Retrieval is followed by `assess_evidence`;
an insufficient result must stop before any LLM call. `verify_legal_citations`
rejects unknown, duplicate, mismatched, or fabricated quoted evidence.

No legal source is treated as authoritative solely because its text sounds
legal. Corpus dataset quality, completeness, currency, and parsing accuracy
remain explicit limitations.

## Evaluation foundation

The legal package provides deterministic baselines for Recall@k, MRR, nDCG,
citation correctness, and unsupported-claim rate. Retrieval and generation
failures remain separate: an empty/insufficient evidence gate is retrieval
failure; an invalid citation or unsupported generated claim is generation or
evidence-validation failure.

Phase 10 does not change Phase 8 risk severity, add agents, authentication,
full observability, caching, frontend code, or production-scale corpus data.

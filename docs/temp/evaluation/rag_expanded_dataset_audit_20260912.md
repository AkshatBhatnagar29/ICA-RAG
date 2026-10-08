# Expanded RAG dataset audit — 2026-09-12

## Dataset and provenance

`data/evaluation/golden/standard_agreement_v2.json` contains 55 unique cases
covering 12 categories. Every case is pinned to the restored canonical
`document_version_id`:

`d89c42a8-0cf3-489d-89a7-e76b3b12ced1`

The source is `Standard-agreement.pdf`, SHA-256
`b720a8c0914608680f2001a0dc709b63c8f71ae0344e18809176962ebed37907`.
The local artifact validation passed: the document is READY, the processed
artifact exists, there are 42 chunks and 42 embeddings, required metadata is
present, all evidence anchors resolve, and the seeded legal corpus reference
`694e8846-51ef-55b8-83e3-62c056d7349a` exists.

The raw directory contains many case-law PDFs, but no second verified contract
artifact suitable for this contract benchmark. The benchmark is therefore
single-contract and its limitation is intentional; case-law PDFs were not
recast as contracts and no synthetic contract evidence was added.

Six cases are explicitly non-retrieval “not stated” checks (automatic renewal,
indemnity, liability cap, confidentiality survival, and IP assignment). The
retrieval baseline consequently covers 49 cases. They remain available for a
future generation/safety harness.

## Schema and validation

The new Pydantic schema is in
`app/services/evaluation/golden_dataset.py`. It adds pinned document identity,
source checksum/provenance, difficulty, legal corpus references, evidence
locators, evidence-group semantics, insufficient-evidence policy, retrieval
applicability, and hard-negative relationships. The original v1 JSON shape is
still accepted by the existing runner.

Validation is implemented by `scripts/validate_golden_dataset.py` and the
result is stored in `data/evaluation/results/golden_dataset_validation.json`.
It checks duplicate IDs, declared document versions, READY state, processed
artifact presence, chunks, embeddings, metadata, evidence anchors/chunk IDs,
legal corpus references, and answer-leakage diagnostics. Result: **valid**.

## Expanded retrieval baseline

Run configuration: existing `intfloat/multilingual-e5-small` embeddings,
existing reranker, production `base` chunking, equal-weight RRF with `k=60`.
No retrieval implementation or model was changed for this dataset work.

| Method | Cases | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 | Mean ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Dense | 49 | .551 | .653 | .714 | .776 | .625 | .654 | .857 | 85.1 | 14.8 | 22.0 |
| BM25 | 49 | .510 | .633 | .694 | .735 | .585 | .620 | .837 | 6.6 | 6.1 | 9.2 |
| Hybrid RRF | 49 | .510 | .673 | .694 | .796 | .605 | .629 | .857 | 21.9 | 21.1 | 27.9 |
| Hybrid + reranker | 49 | .571 | .714 | .714 | .755 | .645 | .672 | .857 | 2616.0 | 2566.9 | 3327.6 |

The machine-readable full report, including every case and category, is
`data/evaluation/results/expanded-baseline/retrieval_report.json`.

## Category results

The table below shows the two hybrid paths; dense and BM25 category results
are retained in the machine-readable report.

| Category | n | Hybrid R@1/3/5/10 | Hybrid MRR | Reranked R@1/3/5/10 | Reranked MRR |
|---|---:|---|---:|---|---:|
| contract_factual | 8 | .500/.500/.625/.750 | .543 | .375/.375/.375/.500 | .393 |
| obligation | 7 | .429/.714/.714/.714 | .548 | .714/.714/.714/.714 | .714 |
| payment_financial | 6 | .667/1.000/1.000/1.000 | .806 | .667/1.000/1.000/1.000 | .833 |
| termination_notice | 6 | .500/.833/.833/.833 | .667 | .667/.833/.833/.833 | .750 |
| renewal_condition_exception | 3 | 1.000/1.000/1.000/1.000 | 1.000 | .667/1.000/1.000/1.000 | .833 |
| dispute_precedence | 5 | 1.000/1.000/1.000/1.000 | 1.000 | 1.000/1.000/1.000/1.000 | 1.000 |
| risk_analysis | 4 | .250/.500/.500/.750 | .417 | .500/.750/.750/.750 | .625 |
| insufficient_evidence | 4 | .250/.250/.250/.500 | .292 | .000/.500/.500/.500 | .208 |
| legal_scope_required | 3 | .000/.000/.000/.667 | .097 | .333/.333/.333/.667 | .370 |
| mixed_contract_legal | 2 | .000/.500/.500/.500 | .250 | .500/.500/.500/.500 | .500 |
| citation_integrity | 1 | 1.000/1.000/1.000/1.000 | 1.000 | 1.000/1.000/1.000/1.000 | 1.000 |

Chunk diagnostics are 42 chunks, mean 59.55 tokens, median 33.5, minimum 2,
maximum 413, 27 below 50 tokens, 13 below 25, 34 below 80, 36 below 100,
heading/clause cohesion 0.592, evidence containment 0.857, and evidence split
rate 0.0.

## Error taxonomy and interpretation

- **Early-rank miss with candidate present:** the principal failure mode for
  risk, legal-scope, and mixed cases; Candidate Recall@40 remains higher than
  early recall.
- **Sparse contractual wording miss:** visible in factual and obligation
  cases where paraphrased questions do not share exact clause terms.
- **Insufficient-evidence retrieval:** not-stated questions are retained for
  safe-answer evaluation, but are not valid positive retrieval targets.
- **Reranker trade-off:** reranking improves aggregate R@3, MRR, and nDCG@5,
  but remains approximately 2.6 seconds mean latency and reduces factual
  R@1/R@10 on this expanded set.
- **Legal-scope boundary:** contract retrieval alone cannot measure legal
  authority retrieval or legal-answer correctness. The legal corpus reference
  is pinned for downstream mixed evaluation; no legal conclusion is treated as
  a contract gold label.

## Baseline comparison and next step

A direct pre-change comparison on this same 55-case dataset and the same
document version is unavailable: the pre-change captured baseline contains the
original 20-case set only. The historical 20-case results remain unchanged in
`docs/evaluation/rag_baseline_20260912.md`; cross-dataset numerical deltas would
not be valid, so none are claimed here.

No retrieval tuning is recommended from this run. The next measurement should
be a second real contract artifact (or a clearly separate legal benchmark) and
then a repeat of this harness with the same schema. RRF-k, weighted fusion, and
reranker experiments should remain frozen until that data limitation is
resolved.

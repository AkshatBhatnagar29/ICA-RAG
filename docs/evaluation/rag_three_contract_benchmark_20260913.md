# Three-contract retrieval generalization benchmark — 2026-09-13

This is a frozen-system evaluation. No embedding, chunking, BM25, RRF, candidate, reranker, prompt, or production-default tuning was performed.

## Contract #3 provenance and ingestion

MeitY's official eGov Standards PDF was acquired as `CONTRACT_TEMPLATE / MASTER_SERVICE_AGREEMENT_TEMPLATE`, not as an executed contract. It is pinned to document version `bf3e4f37-f785-4167-a068-79dfad1d6466`, with 50 pages, 232 chunks, and 232 embeddings. The validated dataset contains 38 cases: 34 retrieval cases and 4 insufficient-evidence safety cases.

See `meity_cloud_msa_acquisition_report.json`, `meity_cloud_msa_ingestion_report.json`, `meity_cloud_msa_golden_validation.json`, and `meity-cloud-msa-baseline/chunking_report.json` for machine-readable provenance and diagnostics.

## Frozen benchmark metrics

| Method | n | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 | Mean ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vector_only | 116 | 0.451 | 0.661 | 0.747 | 0.784 | 0.578 | 0.613 | 0.888 | 37.6 | 19.6 | 27.2 |
| bm25 | 116 | 0.434 | 0.583 | 0.647 | 0.710 | 0.525 | 0.545 | 0.816 | 50.8 | 49.4 | 114.7 |
| hybrid | 116 | 0.460 | 0.652 | 0.698 | 0.779 | 0.571 | 0.590 | 0.879 | 70.8 | 68.8 | 133.3 |
| hybrid_reranked | 116 | 0.511 | 0.747 | 0.784 | 0.810 | 0.634 | 0.668 | 0.879 | 4453.0 | 3986.5 | 7945.1 |

## Per-contract results

### Contract #1

| Method | n | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 | Mean ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vector_only | 49 | 0.551 | 0.653 | 0.714 | 0.776 | 0.625 | 0.654 | 0.857 | 59.7 | 17.3 | 45.9 |
| bm25 | 49 | 0.510 | 0.633 | 0.694 | 0.735 | 0.585 | 0.620 | 0.837 | 8.4 | 8.7 | 10.7 |
| hybrid | 49 | 0.510 | 0.673 | 0.694 | 0.796 | 0.605 | 0.629 | 0.857 | 29.1 | 27.1 | 54.2 |
| hybrid_reranked | 49 | 0.571 | 0.714 | 0.714 | 0.755 | 0.645 | 0.672 | 0.857 | 3583.9 | 3756.6 | 4664.2 |

### Contract #2

| Method | n | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 | Mean ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vector_only | 33 | 0.333 | 0.636 | 0.758 | 0.758 | 0.498 | 0.558 | 0.909 | 20.8 | 20.8 | 23.0 |
| bm25 | 33 | 0.273 | 0.455 | 0.485 | 0.606 | 0.375 | 0.385 | 0.727 | 111.5 | 109.7 | 129.4 |
| hybrid | 33 | 0.303 | 0.515 | 0.636 | 0.727 | 0.433 | 0.469 | 0.848 | 132.0 | 129.7 | 162.0 |
| hybrid_reranked | 33 | 0.394 | 0.818 | 0.818 | 0.818 | 0.576 | 0.630 | 0.848 | 3001.8 | 2874.6 | 4250.8 |

### Contract #3 (MeitY)

| Method | n | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 | Mean ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vector_only | 34 | 0.422 | 0.696 | 0.784 | 0.824 | 0.586 | 0.608 | 0.912 | 22.1 | 20.6 | 28.3 |
| bm25 | 34 | 0.480 | 0.637 | 0.735 | 0.775 | 0.584 | 0.591 | 0.873 | 53.1 | 50.4 | 70.3 |
| hybrid | 34 | 0.539 | 0.755 | 0.765 | 0.804 | 0.655 | 0.653 | 0.941 | 71.4 | 70.4 | 75.6 |
| hybrid_reranked | 34 | 0.539 | 0.725 | 0.853 | 0.882 | 0.676 | 0.699 | 0.941 | 7114.0 | 6956.8 | 8931.9 |

## Contract #3 category matrix

Categories with fewer than three cases are directional only and are not used for broad claims.

| Category | n | Hybrid R@1/R@3/R@5/R@10 | Hybrid MRR | Reranked R@1/R@3/R@5/R@10 | Reranked MRR | Candidate R@40 |
|---|---:|---|---:|---|---:|---:|
| confidentiality_or_data | 5 | 1.000/1.000/1.000/1.000 | 1.000 | 0.800/1.000/1.000/1.000 | 0.900 | 1.000 |
| contract_factual | 6 | 0.333/0.667/0.667/0.667 | 0.444 | 0.333/0.667/0.667/0.833 | 0.517 | 1.000 |
| dispute_resolution | 2 | 0.167/0.833/1.000/1.000 | 0.667 | 0.167/0.833/1.000/1.000 | 0.750 | 1.000 |
| indemnity_or_liability | 2 | 0.500/0.500/0.500/0.500 | 0.500 | 1.000/1.000/1.000/1.000 | 1.000 | 1.000 |
| obligation | 8 | 0.750/0.875/0.875/0.875 | 0.812 | 0.625/0.750/1.000/1.000 | 0.744 | 1.000 |
| payment_financial | 4 | 0.500/1.000/1.000/1.000 | 0.750 | 0.500/0.500/1.000/1.000 | 0.613 | 1.000 |
| risk_analysis | 2 | 0.000/0.000/0.000/0.167 | 0.071 | 0.000/0.000/0.000/0.000 | 0.000 | 0.500 |
| service_level | 2 | 0.000/0.500/0.500/1.000 | 0.321 | 1.000/1.000/1.000/1.000 | 1.000 | 1.000 |
| termination_notice | 3 | 0.667/0.667/0.667/0.667 | 0.667 | 0.333/0.667/0.667/0.667 | 0.500 | 0.667 |

## Cross-document error taxonomy

The case-level taxonomy is in `three_contract_error_taxonomy.json`. It classifies every case that missed R@10 after reranking using candidate recall, hard-negative links, and category/query structure. It is an evaluation taxonomy, not a claim that one mechanism is proven causal.

| Document | Candidate failures | Ranking/fusion | Hard-negative confusion | Risk/query difficulty | Insufficient evidence | Other |
|---|---:|---:|---:|---:|---:|---:|
| Contract #1 | 6 | 3 | 0 | 1 | 2 | 0 |
| Contract #2 | 5 | 1 | 0 | 0 | 0 | 0 |
| Contract #3 (MeitY) | 3 | 1 | 0 | 0 | 0 | 0 |

## Generalization analysis

1. Dense retrieval generalizes partially: Contract #3 is stronger than Contract #2 at R@1/R@3/R@10 and has Candidate R@40 0.912, but it remains below Contract #1 at R@1 and R@3.
2. BM25 also generalizes partially: MeitY reaches R@1 0.480 and R@10 0.775, above Contract #2 but below Contract #1 at R@10; exact terminology helps this document.
3. Hybrid does not consistently improve every document: it improves Contract #3 over dense at R@1/R@3 and Candidate R@40, but is below dense for Contract #1 R@3/R@5 and Contract #2 at R@3/R@5.
4. Reranking consistently improves early ranking in aggregate and improves Contract #3 R@5/R@10/MRR/nDCG, but not Contract #3 R@1; it also lowers Contract #1 R@10. The gain is not uniform.
5. Repeating failures are early-rank confusion with evidence still in the candidate pool, plus multi-provision risk questions. These are visible across the contracts, though magnitude varies.
6. Document-specific behavior is strongest in MeitY's exact clause terminology and high heading/clause cohesion (0.698), while Contract #2 has many short chunks and lower cohesion; this is correlation, not a causal result.
7. Long-document fragmentation is not supported as a universal explanation: MeitY has 232 chunks, median 109 tokens, and high evidence containment (0.953), yet still has hard early-rank misses; Contract #2's 669 chunks and median 20 tokens remain a stronger structure-specific concern.
8. The measured pattern is primarily ranking/query-type difficulty for MeitY risk cases, with some candidate weakness in indemnity/liability and termination. It is not a consistently weak Candidate R@40 result.

## Next decision gate

Decision C is the best-supported next experiment: run a controlled reranker comparison because Candidate R@40 remains strong (0.879 combined; 0.941 for MeitY hybrid) while early-rank confusion remains. Keep the current reranker and all frozen retrieval defaults unchanged during that experiment. A separate chunking experiment is not yet justified as the immediate next step, although Contract #2 structure should remain a preregistered covariate.

Insufficient-evidence cases were excluded from retrieval recall by design and remain safety-answer cases. No production-default changes were made.

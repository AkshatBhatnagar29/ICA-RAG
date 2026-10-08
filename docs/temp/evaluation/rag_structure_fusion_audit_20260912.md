# RAG structure and fusion audit — 2026-09-12

This note records the first implementation increment after the captured
baseline in `rag_baseline_20260912.md`. The baseline artifacts remain the
reference measurements and were not rewritten by this change.

## Baseline evidence

The pinned 20-case `Standard-agreement.pdf` benchmark reported:

| Retriever | R@1 | R@3 | R@5 | R@10 | MRR | Candidate R@40 |
|---|---:|---:|---:|---:|---:|---:|
| Dense | 0.225 | 0.475 | 0.525 | 0.983 | 0.328 | 0.983 |
| BM25 | 0.650 | 0.875 | 0.983 | 0.983 | 0.722 | 0.983 |
| Equal-weight RRF | 0.275 | 0.725 | 0.983 | 0.983 | 0.443 | 0.983 |
| RRF + reranker | 0.475 | 0.858 | 0.983 | 0.983 | 0.589 | 0.983 |

Chunking was 16 chunks with median 26.5 tokens, 11 chunks below 50 tokens,
and 0% measured heading/clause cohesion. These values are historical baseline
measurements, not acceptance values hardcoded into the implementation.

## Implemented increment

PDF page-sized extraction blocks are now decomposed at conservative,
line-start legal markers before block classification. Recognized markers
include numbered and parenthesized clauses, schedules/annexures,
article/section/clause labels, selected title-like headings, and all-caps
headings. Bare numeric markers are joined to their continuation line, so a
marker cannot become a standalone evidence chunk. Derived blocks retain page,
bounding-box, and deterministic block-position provenance.

RRF now accepts explicit non-negative dense and sparse weights while preserving
the existing equal-weight default. This enables controlled comparisons of
`k=20,40,60,100` and sparse-preferred variants without changing the embedding
model or introducing a second retrieval system.

The retrieval evaluator now records nDCG@5, p50/p95 latency, and additional
small-chunk thresholds. Its report records the experiment name, RRF settings,
embedding model, reranker model, and exact document version.

## Verification

- Focused indexing/retrieval/evaluation tests: 26 passed.
- Ruff for changed application, script, and test paths: passed.
- Full host suite: 93 passed, 2 skipped, 1 Windows temp-directory cleanup
  error. The error is environment-specific (`WinError 5` while pytest removes
  `.pytest-host-tmp`); it is not a retrieval assertion failure.

## Final selected-base measurement

The canonical source was restored and reindexed under the original document
version. The selected `base` chunker produced 42 chunks. The exact 20-case
benchmark then reported:

| Retriever | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Dense | 0.450 | 0.575 | 0.625 | 0.842 | 0.490 | 0.463 | 0.983 |
| BM25 | 0.500 | 0.850 | 0.850 | 0.892 | 0.614 | 0.619 | 0.983 |
| Hybrid RRF | 0.450 | 0.650 | 0.875 | 0.942 | 0.551 | 0.575 | 0.983 |
| Hybrid + reranker | 0.700 | 0.742 | 0.767 | 0.892 | 0.688 | 0.650 | 0.983 |

The hybrid regression guard still fails at R@3 and MRR versus BM25. Weighted
RRF (0.3:0.7 and 0.2:0.8 dense:sparse) did not satisfy all guard metrics.
RRF k=20/40/60/100 produced the same rankings on this dataset, while the
score arithmetic changed as expected. Candidate Recall@40 is now invariant
before and after reranking, confirming reranking only reorders candidates.

The `refined` chunking experiment produced 52 chunks and reduced hybrid early
ranking, so it was not selected. The embedding model, reranker model, and
default equal-weight RRF behavior remain unchanged. The current reranker is
experimentally optional because its R@1/MRR gain costs approximately 2.37
seconds mean latency and reduces R@3–R@10.

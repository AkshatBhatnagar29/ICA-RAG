# ICIA RAG baseline and bottleneck audit

This report is based on the production PostgreSQL rows for the READY
`Standard-agreement.pdf` version and the checked-in 20-case golden dataset.
The benchmark was run on 2026-09-12 with the existing FastEmbed providers.
It is an evaluation baseline, not a production model change.

## Pipeline found in the repository

```text
PDF/DOCX
  -> PyMuPDF block extraction (DOCX parser for DOCX)
  -> page/block normalization and numbered/all-caps block classification
  -> Tesseract fallback for image-only PDF pages
  -> hierarchical page/heading-aware chunker
  -> FastEmbed multilingual-e5-small, passage/query prefixes, 384 dimensions
  -> PostgreSQL pgvector cosine distance with HNSW cosine operator class
  -> request-local BM25 over authorized chunks
  -> reciprocal-rank fusion (k=60)
  -> optional jina-reranker-v1-tiny-en cross-encoder
  -> bounded evidence packet (6,000 estimated tokens)
  -> structured LLM output
  -> fail-closed citation validation
```

Pages, extraction method, section/clause fields, and source block provenance
are persisted on chunks. The PDF fallback invokes the configured Tesseract
executable with bounded subprocess arguments. DOCX native processing does not
invent physical page numbers; optional conversion is handled elsewhere in the
processing pipeline.

## Measured baseline

The standalone benchmark is in `data/evaluation/results/retrieval_report.json`.

| Configuration | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
| Dense/vector only | 0.225 | 0.475 | 0.525 | 0.983 | 0.328 | 136 ms |
| BM25 | 0.650 | 0.875 | 0.983 | 0.983 | 0.722 | 6 ms |
| Current hybrid (RRF) | 0.275 | 0.725 | 0.983 | 0.983 | 0.443 | 25 ms |
| Hybrid + current reranker | 0.475 | 0.858 | 0.983 | 0.983 | 0.589 | 1,954 ms |

The reranker candidate pool preserved 0.983 Recall@40. Therefore the relevant
evidence was generally retrieved before reranking; reranking improved early
rank but did not improve Recall@5 and added approximately 1.9 seconds per
query in this environment.

### Chunking measurements

For one six-page production document: 16 chunks, mean 156 tokens, median 26.5,
minimum 2, maximum 644, 11 chunks under 50 tokens, and 6.25% exact duplicate
text ratio. The golden evidence anchors were fully contained in one chunk at
95.65%; no anchor was identified as split across adjacent chunks by the
anchor-based check. Explicit heading-plus-clause metadata cohesion was 0% for
this PDF because the parser classified the visible clause material as regular
text rather than preserving numbered clause headings as separate structured
heading blocks. This is a structure-detection weakness, not evidence that the
text itself was lost.

### Golden and generation checks

The full 20-case `--no-llm` run now reports 20 `RETRIEVAL_ONLY` cases, zero
errors, and 95% expected-evidence retrieval pass rate. LLM generation is not
scored in that mode.

A five-case real-provider smoke evaluation completed with 5/5 end-to-end
passes, 100% groundedness, 100% citation presence, 100% citation correctness,
and 0% unsupported citations. The existing checked-in full LLM run remains
available in `data/evaluation/results/golden_eval_20260911T140816Z.json` and
reported 20 cases, 55% end-to-end pass rate, 95% groundedness, 82.5% citation
coverage, 77.5% citation correctness, and 2.5% unsupported-citation rate.
Those full-run values are retained as historical evidence because the latest
provider run was intentionally limited to five cases.

## Root-cause ranking

1. **Ranking/score ordering is the highest-impact measured issue.** BM25
   substantially outperformed dense and current RRF on this contract (MRR
   0.7225 vs 0.3280 and 0.4433). The candidate pool is strong, so the lost
   quality is mostly early ordering, not absence of relevant text. Investigate
   query-dependent fusion weights or a cheaper reranking policy before changing
   embedding models.

2. **Chunk/structure metadata is the second issue.** Eleven of sixteen chunks
   are under 50 tokens and explicit clause-heading cohesion is not preserved.
   This can damage ranking and citation navigation even when the anchor text is
   present. Benchmark heading reconstruction and minimum-size merging on a
   larger representative corpus before changing the production chunker.

3. **Generation/citation quality is a downstream issue, not the primary
   retrieval bottleneck.** The historical full run had high groundedness but
   lower answer accuracy and citation coverage. The current evidence packet is
   bounded and fail-closed; remaining failures should be classified from the
   per-case generation and citation reports rather than attributed to retrieval
   automatically.

## Conclusion

ICIA is currently limited primarily by **D: vector/fusion ranking quality**,
with **B: chunk/structure quality** as the next justified investigation area.
It is not currently justified to replace the embedding model or permanently
enable the reranker: the existing candidate pool reaches 98.3% Recall@40,
while the reranker adds substantial latency and only improves early rank.

## Reproducible commands

```text
uv run python scripts/inspect_chunks.py --document Standard-agreement.pdf --json data/evaluation/results/chunks_standard_agreement.json
uv run python scripts/evaluate_retrieval.py
uv run python scripts/run_golden_eval.py --no-llm
uv run python scripts/run_golden_eval.py --limit 5
```

The host-native database credential mismatch is documented in `AGENTS.md`; the
measurements above used the healthy Compose PostgreSQL service through its
published port and did not change credentials or authentication settings.

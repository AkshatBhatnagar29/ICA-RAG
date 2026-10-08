# Reranker final decision — 2026-09-13

## Status: decision gate open

No production reranker change is approved from this run. The requested matched protocol was started with the frozen 116-case, 40-candidate cache, three warm-ups, five measured repetitions per case, batch size 8, one CPU thread, and identical timing boundary. Jina was still CPU-bound after approximately one hour and was stopped before the evaluator emitted a complete result file; MiniLM was therefore not run under the same protocol.

The previous report is not sufficient for a final decision because it used three Jina repetitions versus one MiniLM repetition. Its directional quality result remains:

| Model | R@1 | R@3 | MRR | nDCG@5 | Mean ms | Candidate R@40 |
|---|---:|---:|---:|---:|---:|---:|
| Jina tiny (old protocol) | 0.511 | 0.747 | 0.639 | 0.668 | 4211.8 | 0.879 |
| MiniLM (old protocol) | 0.598 | 0.753 | 0.691 | 0.708 | 3589.7 | 0.879 |

Those figures must not be described as matched latency or resource evidence. No quality improvement, latency difference, or memory difference is approved until both models complete the same protocol. The current application default remains Jina and `RERANKER_ENABLED=false`; this is an intentional hold, not a claim that Jina is the quality winner.

## Reproduction

```sh
uv run python scripts/run_reranker_experiment.py --model A_current_jina --repetitions 5 --warmups 3 --threads 1 --batch-size 8 --max-length 512 --output-dir reports/productionization/matched_reranker
uv run python scripts/run_reranker_experiment.py --model B_minilm_l6 --repetitions 5 --warmups 3 --threads 1 --batch-size 8 --max-length 512 --output-dir reports/productionization/matched_reranker
```

The script now records p99, peak process RSS, process CPU time/utilization, throughput, success/timeout/exception counts, and reranker-only timing. Retrieval, embedding, BM25, RRF, database, and LLM timings remain separate and are not included in the reranker timing boundary.

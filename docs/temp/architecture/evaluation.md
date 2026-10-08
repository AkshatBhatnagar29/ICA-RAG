# Evaluation architecture

Phase 13 evaluation is an offline, deterministic boundary under
`app/services/evaluation/`. It consumes immutable source-derived benchmark
records and never changes application runtime, raw datasets, tenant data, or
canonical evidence.

`data/evaluation/retrieval/retrieval_v1.json` is a small real-source benchmark.
Contract labels come from the labeled clause dataset and are silver labels;
legal records are source-document identity heuristics. There are no fabricated
gold answers. Contract and legal records retain separate corpus namespaces and
source paths.

The runner reports Recall@1/5/10, Precision@1/5/10, MRR, nDCG@1/5/10, and
measured p50/p95 latency for the existing E5 dense provider, BM25 baseline,
RRF hybrid, and local cross-encoder reranker. This benchmark uses an in-memory
authorized corpus projection so it exercises the production retrieval adapters
without changing runtime or tenant data; database-backed end-to-end retrieval
remains a separate integration check.
Citation precision/recall, unsupported-claim rate, and agent metrics are
available as deterministic library functions and must remain independent of
fluency. Unknown, duplicate, cross-tenant, cross-document, wrong-page, and
mixed-namespace citations are fail-closed application cases, not quality credit.

Run `uv run python scripts/evaluate.py --dataset retrieval_v1 --top-k 5`.
Results are JSON under `data/evaluation/results/` and include timestamp and
environment metadata. Results are local artifacts and must not contain secrets.

This v1 is too small for a reliable train/validation/test split and is not a
production SLA or legal-accuracy claim. Retrieval tuning must use separate
development data; the benchmark is held out from threshold tuning. LLM judges,
if later added, are secondary non-authoritative signals.

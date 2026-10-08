# Hybrid retrieval

`RetrievalService.search()` normalizes the query, requires tenant scope, chooses
a candidate size, runs dense and/or sparse search, and fuses results. Dense
search uses E5 query vectors and pgvector cosine distance. Sparse search uses
BM25 over authorized metadata. `reciprocal_rank_fusion()` merges by chunk UUID:

`RRF(d) = sum_m weight_m / (k + rank_m(d))`, with `k=60`.

RRF is rank-based, so dense scores and BM25 scores do not need calibration.
Equal weights are current defaults. Ties are broken by UUID. The reranker then
scores `(query, chunk text)` pairs and only reorders the existing candidate set.

There are three distinct quantities:

1. retrieval/reranker candidate pool (`RERANKER_CANDIDATE_K=40` in the frozen
   experiment/runtime setting);
2. reranked results exposed to a request;
3. generation evidence (`GENERATION_TOP_K=10`, separately bounded by 6000 text
   tokens).

The source implementation derives request-time `candidate_k` from request
`top_k` and uses the configured reranker limit when reranking is requested;
the experiment harness freezes exactly 40 common candidates. Do not equate the
experiment's 40 with the LLM's context size.

# Phase 6 reranking architecture

Phase 6 adds optional local cross-encoder reranking after the existing Phase 5
retrieval pipeline. The security order is unchanged:

`authorized scope -> dense/BM25 -> RRF candidate set -> cross-encoder -> final top-K`

## Model decision

The selected adapter is FastEmbed 0.8.0's ONNX `TextCrossEncoder` with
`jinaai/jina-reranker-v1-tiny-en`. FastEmbed's installed registry reports an
approximate 0.13 GB model and Apache-2.0 license. The model is English,
local-only, CPU-capable, and supports long inputs. The registry also exposes
larger alternatives; `BAAI/bge-reranker-base` was not selected initially
because its reported size is approximately 1.04 GB and its CPU cost is higher.
This is an operational choice, not a claim that it is superior on ICIA data.

FastEmbed is already a production dependency for embeddings, so no new ML
framework or database is introduced. The concrete model is hidden behind the
application-owned `Reranker` protocol.

## Candidate and scoring semantics

RRF remains candidate generation. RRF and cross-encoder scores are not added:
the reranker score determines ordering only within the RRF candidate set, while
both scores and both ranks remain available for diagnostics. Defaults are:

- `RERANKER_CANDIDATE_K=40`
- `RERANKER_TOP_K=5` (the request's `top_k` remains the response limit)
- `RERANKER_BATCH_SIZE=8`
- `RERANKER_MAX_LENGTH=512`
- `RERANKER_THREADS=1`

The model receives `(query, candidate_chunk_text)`. Candidate text is data,
not instructions; no metadata is concatenated and no text is rewritten.
Duplicate chunk IDs are removed, malformed/empty text fails explicitly, and
ties are ordered by ascending chunk ID. The model is instantiated once per
application process and reused across requests.

## Cache and operations

Weights are stored under `RERANKER_CACHE_PATH`, defaulting to
`data/model-cache/reranker` locally and `/app/data/model-cache/reranker` in the
container. The existing Docker `model_cache` named volume mounts
`/app/data/model-cache`; `docker compose down` preserves it, while
`docker compose down -v` removes named volumes. Weights are never committed to
Git or stored in document data directories.

## Diagnostics and limitations

Search diagnostics expose whether reranking ran, model identifier/version,
candidate/final counts, batch size, and measured inference latency. Model paths
and host resource details are not exposed by the API. An explicit reranking
failure returns a clear service error; disabled reranking follows the exact
Phase 5 result path.

The labeled fixture in `data/evaluation/reranking_fixture.json` and
`scripts/evaluate_reranking.py` is a developer fixture / sanity evaluation,
not production retrieval quality. Actual latency/cache measurements should be
recorded from the environment running the script; no quality improvement is
claimed without those measurements.

Observed Windows CPU measurements on 2026-09-04:

- first model download and initialization: 41,172 ms
- warm initialization from cache: 1,036 ms
- cache size: 134,388,573 bytes
- inference: 17.04 ms (5 candidates), 33.89 ms (10), 73.99 ms (20), 136.21 ms (40)
- CPU utilization and process RSS: NOT VERIFIED as a controlled measurement

The synthetic sanity evaluation observed MRR 0.8750, Recall@8 1.0000, and
nDCG 0.9077. The result is not evidence of production quality.

## Windows manual verification

```powershell
docker compose up -d
docker compose ps
docker compose exec api uv run --no-dev alembic upgrade head
docker compose exec api uv run python scripts/seed_retrieval_fixture.py
docker compose exec api uv run python scripts/search.py "termination notice period" --tenant-id 9f61566b-d9fb-5bbd-99fd-23831653ce34 --mode hybrid
docker compose exec api uv run python scripts/search.py "termination notice period" --tenant-id 9f61566b-d9fb-5bbd-99fd-23831653ce34 --mode hybrid --rerank
uv run python scripts/evaluate_reranking.py
```

Repeat the last search for `indemnification`, `limitation of liability`,
`automatic renewal`, `governing law India`, `thirty days prior written notice`,
and `12.3(a)`. The reranked command prints RRF rank, reranker score, final
rank, and a comparison for every returned chunk.

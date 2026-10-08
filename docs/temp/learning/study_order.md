# Dependency-aware study order

## Level 0: Python prerequisites

Read async/await, context managers, dataclasses, protocols, type narrowing,
exceptions, UUIDs, hashing, JSON, and list/dict comprehensions. Practise by
reading `app/services/retrieval/models.py` and `app/services/generation/context.py`.

## Level 1: process startup and boundaries

1. `app/core/config.py` - settings and environment mapping.
2. `app/main.py` - object graph and lifespan.
3. `app/api/router.py`, `app/api/v1/router.py` - route assembly.
4. `app/core/exceptions.py`, `app/core/logging.py` - safe failures/logging.

## Level 2: database and identity

1. `app/db/base.py`, `app/db/session.py`.
2. `app/models/auth.py`, `app/security/auth.py`.
3. `app/models/document.py`, `chunk.py`, `legal.py`, analysis/comparison models.
4. Migrations `0001` through `0008` in order.

## Level 3: documents and indexing

Read `ingestion/validation.py`, `documents.py`, `storage.py`,
`processing_models.py`, `parser.py`, `pipeline.py`, `structure.py`, then
`indexing/chunking.py`, `embeddings.py`, `indexing/service.py`.

## Level 4: retrieval

Read `retrieval/query.py`, `models.py`, `bm25.py`, `fusion.py`, `service.py`,
then `reranking/models.py` and `reranking/service.py`.

## Level 5: generation and citations

Read `generation/context.py`, `prompts.py`, `llm.py`, `output.py`,
`citations.py`, `service.py`, then `agents/synthesis.py`.

## Level 6: product intelligence

Read `contracts/extraction.py`, `schemas.py`, `evidence.py`, `risks.py`,
`service.py`, and comparison modules. Then read legal models/query/retrieval.

## Level 7: agents

Read `agents/models.py`, `router.py`, `planner.py`, `registry.py`, `executor.py`,
`service.py`, `synthesis.py`.

## Level 8: evaluation and operations

Read evaluation services, `scripts/prepare_reranker_experiment.py`,
`run_reranker_experiment.py`, the frozen reports, then Docker and deployment
docs.

For every level, pair source reading with its nearest tests. Do not start with
templates, generated reports, or model caches.

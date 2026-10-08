# ICIA master study guide

This guide is the index for a source-code-driven study of ICIA. Read it in the
order in [`study_order.md`](study_order.md), not alphabetically.

## Part A - Orientation

- [Repository map](repository_map.md)
- [Technology map](technology_map.md)
- [Dependency graph](dependency_graph.md)
- [Concept map](concept_map.md)
- [Study order](study_order.md)

## Part B - Backend and data

- [Request lifecycle](request_lifecycle.md)
- [Database](database.md)
- [Security and auth](security_auth.md)
- [Redis](redis.md)

## Part C - Documents and indexing

- [Ingestion](ingestion.md)
- [Chunking](chunking.md)
- [Embeddings](embeddings.md)
- [Models](models.md)

## Part D - RAG

- [BM25](bm25.md)
- [Retrieval](retrieval.md)
- [pgvector](pgvector.md)
- [Reranking](reranking.md)
- [Context builder](context_builder.md)
- [Generation](generation.md)
- [Citations](citations.md)

## Part E - Product intelligence

- [Contract intelligence](contract_intelligence.md)
- [Comparison](comparison.md)
- [Legal RAG](legal_rag.md)
- [Agent](agent.md)

## Part F - Quality and operations

- [Evaluation](evaluation.md)
- [Testing](testing.md)
- [Observability](observability.md)
- [Security](security.md)
- [Production](production.md)
- [UI](ui.md)

## Part G - Rebuilding and interviews

- [Architecture decisions](architecture_decisions.md)
- [File dependency graph](file_dependency_graph.md)
- [Rebuild from scratch](rebuild_from_scratch.md)
- [System-design interview preparation](system_design_interview.md)
- [Why questions](why_questions.md)

## Truth status

The current code is the authority. The guide deliberately calls out future
architecture (caching, legal reasoning, background processing, large-scale
sparse indexing) rather than presenting it as implemented.

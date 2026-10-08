# RAG Architecture

Parser -> Chunker -> Embeddings -> Dense retrieval + BM25 -> RRF -> Reranker -> Context builder -> LLM -> citation verification.
# Retrieval Architecture

Retrieval is not implemented in Phase 1. The application retains the planned
boundary for a later application-owned pipeline: dense retrieval and sparse
retrieval combined with reciprocal rank fusion, optional reranking, controlled
context construction, and evidence-backed generation.

No LLM, embedding model, document parser, OCR, or retrieval framework is
introduced during foundation work.

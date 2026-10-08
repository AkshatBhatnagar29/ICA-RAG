# Chunking and Indexing (Phase 4)

Phase 4 converts the Phase 3 `ProcessedDocument` artifact into deterministic,
structure-aware chunks. Headings and the blocks beneath them form logical
units; complete units are retained when possible. Oversized units are split
recursively at block/paragraph, sentence, and finally token boundaries. The
hard limit is enforced only at the final necessary boundary.

Defaults are a 600-token target, 1,000-token soft maximum, 1,500-token hard
maximum, 40-token configurable overlap setting, and embedding batches of 32.
Normal clause-level chunks receive no mechanical overlap. The current splitter
keeps overlap disabled unless a future structural splitter explicitly needs it.

Chunk text is NFC-normalized using the Phase 3 policy and is never summarized,
paraphrased, or rewritten. Tables are emitted as coherent table chunks with
their source rows and page/block provenance. Every chunk stores tenant,
document/version, hierarchy, section/clause metadata, chunk type, hashes,
physical pages, optional printed label, extraction method, and source blocks.
Printed page labels are never inferred from physical page numbers.

Chunk identity is deterministic for a version, structural unit, piece position,
and text. A unique constraint makes repeated indexing idempotent. Existing
vectors with the same content and embedding configuration can be reused,
including across document versions. Version isolation is enforced by a
composite foreign key; tenant scope is required by the indexing service and is
checked against an assigned document tenant.

PostgreSQL with pgvector remains the single vector store. The embedding
provider is local CPU `intfloat/multilingual-e5-small` through the maintained
`fastembed` ONNX runtime. Because FastEmbed 0.8.0 does not list this model,
the application registers the exact Hugging Face model through FastEmbed's
custom-model API, pointing at its published `onnx/model.onnx` and tokenizer
files, with mean pooling, normalization, and dimension 384. It uses
`passage:` for documents and `query:` for queries. Both use the same provider
and configured 384-dimensional output.
The database has a cosine HNSW index with conservative defaults `m=16` and
`ef_construction=64`; these parameters should be evaluated later with real
retrieval workloads. Model weights are runtime-cached and are not committed.

The ORM metadata represents the vector type, dimension check, and HNSW index;
the migration uses the same pgvector type and operator class. With the rebuilt
image, `alembic check` reports no drift.

Phase 5 will add dense/BM25 retrieval, metadata filtering, and RRF. Phase 6
will evaluate reranking. Phase 7 will add context construction, Groq
generation, structured output, and citation verification. None of those are
implemented here.

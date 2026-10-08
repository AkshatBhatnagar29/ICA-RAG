# PostgreSQL and pgvector

PostgreSQL is the durable system of record. `Chunk.embedding` and
`LegalChunk.embedding` are pgvector columns with configured dimensions and HNSW
cosine indexes. HNSW builds a graph of approximate nearest-neighbor connections;
`m` controls graph connectivity and `ef_construction` build quality/memory.

`RetrievalService.dense()` constructs a SQLAlchemy query that first applies
tenant, document, version, and optional structural filters, then orders by
cosine distance and limits candidates. This ordering matters: unauthorized
rows never become evidence candidates. BM25 is not pgvector; it is an in-process
lexical scorer over the authorized rows.

PostgreSQL + pgvector was selected to keep metadata, authorization predicates,
transactions, and vectors in one operational boundary. Pinecone/Qdrant/Chroma
could provide specialized ANN, but introduce another consistency and tenancy
boundary without measured need. Elasticsearch/OpenSearch could supply persistent
BM25, but current corpus size does not justify it.

# Data Architecture

PostgreSQL stores application metadata. pgvector stores embeddings. Object
storage stores raw documents and processed representations. Redis provides
cache/state infrastructure.

Phase 1 provides the PostgreSQL connection pool, async SQLAlchemy session
factory, Redis client, and Alembic migration boundary. Phase 2 adds `documents`
and immutable `document_versions`; each uploaded file is stored under generated
document/version identifiers, never the client filename.

Phase 3 stores the canonical processed representation as
`documents/{document_id}/versions/{version_id}/processed/document.json`. It
contains typed processing metadata, pages, blocks, extraction methods, and
physical page provenance. No Phase 3 relational tables are required. A DOCX
without successful rendering has no invented physical page number.

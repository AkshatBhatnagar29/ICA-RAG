# System Architecture

The system is a modular monolith: Client -> FastAPI -> validation and domain
services -> persistence/object storage. Future retrieval and generation layers
are documented separately and are not part of Phase 3.

Phase 1 establishes FastAPI, PostgreSQL 16 with pgvector, Redis 7, typed
configuration, health/readiness endpoints, request IDs, and safe errors. Phase
2 exposes `POST /api/v1/documents`, validating filename, extension, MIME type,
signature, size, and checksum before immutable version storage.

Phase 3 extends this ingestion boundary with synchronous document processing.
The original remains immutable and a version-specific processed JSON artifact is
written only after parsing succeeds. PDF pages use PyMuPDF and per-page OCR
fallback; DOCX uses python-docx and optional LibreOffice rendering for physical
page provenance. Processing does not perform chunking, indexing, retrieval, or
RAG.

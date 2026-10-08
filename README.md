# Indian Contract Intelligence Agent

Production-first AI system for Indian contract review and intelligence.

## Frozen stack
- Python 3.12 + uv
- FastAPI
- PostgreSQL 16 + pgvector
- Redis 7
- SQLAlchemy 2.x + Alembic
- Docker Compose
- pytest + Ruff + mypy
- OpenTelemetry + Langfuse (later phases)
- Next.js frontend (later phase)

See `docs/architecture/` and `docs/decisions/`.

## Phase 1 local verification

Install dependencies and start the foundation services:

```bash
uv sync
docker compose up --build
```

The API exposes process liveness at `GET /api/v1/health`. This endpoint does
not require PostgreSQL or Redis. Dependency readiness is reported by
`GET /api/v1/ready`, which returns `200` only when both services respond and
`503` otherwise. Both endpoints return an `X-Request-ID` response header.

Run the local quality checks with:

```bash
uv run pytest
uv run ruff check .
uv run mypy app
```

Apply the initial database migration with:

```bash
uv run alembic upgrade head
```

## Document uploads

Phase 2 accepts PDF and DOCX uploads at `POST /api/v1/documents` using multipart
fields `file`, `title`, `document_type`, and optional `description`. Uploads are
limited by `MAX_UPLOAD_SIZE_MB` (25 MB by default), stored locally under
`LOCAL_STORAGE_ROOT`, and assigned immutable versions. Re-uploading identical
content for the same title returns `409 Conflict`; changed content creates the
next version. Parsing and processing are intentionally deferred to later
phases. Phase 3 now processes uploads synchronously and returns `READY` only
after writing a processed artifact. See `docs/architecture/document-processing.md`.

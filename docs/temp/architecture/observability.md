# Phase 14: production observability minimum

ICIA uses one dependency-free, process-local metrics abstraction and JSON
application logs. The ASGI request middleware validates or generates a bounded
`X-Request-ID`, returns it on responses, records HTTP status and latency, and
places it in the logging context. Uvicorn access logs are disabled so each API
request has one structured application log record.

The internal `GET /api/v1/metrics` endpoint exposes counter and latency
snapshots. Metrics cover HTTP requests, dense/BM25/RRF retrieval, reranking,
ingestion/OCR, Groq outcomes, citation validation, and bounded agent execution.
This is intentionally process-local; durable aggregation and alerting are
outside the minimum production observability phase.

Logs use an allowlist for structured fields and redact common credential forms.
Contract/legal text, prompts, provider responses, authorization headers, and
credential fields are not emitted by the application logging layer.

Readiness checks PostgreSQL only. Redis remains available in Compose but is not
used on the current API request path and therefore cannot make the service
appear unready.

# Observability

`RequestIdMiddleware` and `RequestIdFilter` attach request IDs. JSON logging
redacts common secret patterns and allows a deliberately small safe-field set.
`Metrics` is an in-process counter/observation abstraction; retrieval, BM25,
RRF, reranker, LLM, agent, citation, and indexing paths record metrics.

Health endpoints are in `services/health.py` and `endpoints/health.py`;
readiness checks PostgreSQL. Startup configures telemetry but no external tracing
backend is required by current code. Provider logs record response shape/hash
and byte count, not answer content. Generation logs bounded counts, estimated
context tokens, request size, and evidence IDs; they do not log contract/legal
text or secrets.

Trace a request with its request ID from middleware -> endpoint -> retrieval
latency/candidate metrics -> reranker load/inference metrics -> provider
outcome/latency -> citation failure/success -> response. Metrics are process
local, so production aggregation would require a future exporter.

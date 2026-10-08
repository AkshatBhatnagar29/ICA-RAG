# Technology decisions

The canonical rationale is in `docs/decisions/ADR-001` through `ADR-005` and
the architecture docs. In short: FastAPI + SQLAlchemy + Pydantic provide a
typed modular monolith; PostgreSQL + pgvector keeps relational authorization
and vectors together; FastEmbed/E5 gives local repeatable retrieval; BM25 and
RRF hedge semantic/exact-match failure; Jina reranks a bounded candidate pool;
Groq supplies hosted structured synthesis; Alembic makes schema changes
reviewable; Docker Compose keeps local deployment reproducible; Jinja2 obeys the
Python/server-rendered UI constraint.

Rejected/deferred choices are not necessarily bad technologies: Pinecone/Qdrant/
Chroma add a vector service; Elasticsearch/OpenSearch add sparse infrastructure;
LangChain/LlamaIndex add orchestration abstractions; Kafka/Celery add durable
distributed work queues; Kubernetes adds operational overhead; React/Next/Vite/
Node violate the product constraint. Each would require measured scale or an
explicit architecture decision before adoption.

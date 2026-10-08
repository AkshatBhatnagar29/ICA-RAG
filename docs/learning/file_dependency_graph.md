# File dependency graph

## High-level

```text
main.py -> api/v1/router.py -> endpoints
endpoints -> security/auth.py -> models/auth.py + db/session.py
endpoints -> services
services -> models + repositories + providers
retrieval/service.py -> embeddings.py + bm25.py + fusion.py + reranking/service.py
generation/service.py -> retrieval/service.py + context.py + llm.py + citations.py
agents/service.py -> planner/executor/tools -> contracts/legal/retrieval -> synthesis
```

## Core module calls

| File | Calls/imports | DB/external model |
|---|---|---|
| `app/main.py` | constructs all runtime services | settings, SQLAlchemy, FastEmbed, Groq |
| `api/v1/endpoints/chat.py` | `GenerationService.answer` | auth/session/provider |
| `retrieval/service.py` | dense, sparse, RRF, reranker | `Chunk`, pgvector, E5/BM25 |
| `generation/context.py` | creates `EvidenceItem/Packet` | no DB; receives authorized results |
| `generation/service.py` | provider + output/citation validation | Groq protocol |
| `agents/service.py` | tool registry, analysis/comparison/legal, synthesis | domain services and LLM |
| `indexing/service.py` | chunker, embeddings, commits chunks | `DocumentVersion`, `Chunk`, E5 |
| `contracts/service.py` | extraction/evidence/risks/repository | analysis/chunk rows |
| `legal/retrieval.py` | legal scope, fusion/rerank | legal chunk rows + E5 |

For a complete file-by-file relationship view, combine this table with
`repository_map.md`, then use each module's nearest test as the executable
contract. Trivial package markers and generated caches are intentionally LOW
priority.

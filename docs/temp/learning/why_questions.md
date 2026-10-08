# ICIA why questions

| Why? | If removed | Tradeoff/security/performance |
|---|---|---|
| PostgreSQL? | lose relational source of truth | stronger consistency; DB becomes capacity bottleneck |
| pgvector? | no in-DB dense search | avoids second vector service; HNSW costs RAM/build time |
| BM25? | exact identifiers/dates degrade | CPU/materialized authorized set |
| RRF? | score calibration coupling | rank fusion is robust but adds a choice of k/weights |
| reranker? | worse early ordering | CPU latency; cannot add recall |
| E5? | semantic retrieval quality changes | 384D local CPU compromise |
| FastEmbed? | external model service | local privacy/repeatability; RAM/cold load |
| Redis? | no current product behavior changes | reserved infrastructure, not durable truth |
| FastAPI/Pydantic? | weaker typed boundaries | async/validation productivity versus framework coupling |
| agent? | fixed workflow only | tool choice adds capability but requires strict limits |
| legal RAG? | no versioned legal context | separate corpus/provenance avoids citation mixing |
| citations? | unsupported claims appear authoritative | validation costs tokens/implementation but enables auditability |
| evidence registry? | lose provenance/bookkeeping | must separate it from generation context to control prompt size |
| tenant isolation? | cross-customer disclosure | every retrieval/service path must carry scope |
| Jinja2? | need a frontend build/runtime | less interactivity, simpler Python-only deployment |
| Docker? | host drift | image/volume/secret operations become responsibilities |

Scale breakpoints are empirical: BM25 materialization, local model CPU, HNSW
memory, Groq quota, and single-VM database capacity are the first likely ones.

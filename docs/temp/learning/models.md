# Models master table

| Model | Purpose | Input/output | Backend/location | Status |
|---|---|---|---|---|
| `intfloat/multilingual-e5-small` | dense retrieval/indexing | query/document text -> 384D vector | FastEmbed ONNX, local CPU, `embeddings.py` | runtime |
| `jinaai/jina-reranker-v1-tiny-en` | candidate reranking | query + chunk -> scalar score | FastEmbed ONNX, local CPU, `reranking/service.py` | runtime default |
| `Xenova/ms-marco-MiniLM-L-6-v2` | reranker comparison | query + chunk -> scalar score | experiment scripts/cache | evaluation only |
| `openai/gpt-oss-20b` | synthesis/semantic classification | prompts -> JSON/text | Groq HTTP API | configured provider |

Repository source does not establish parameter counts, training details, or
vendor SLAs beyond model identifiers/configuration; do not invent them. E5
dimension is validated at 384. Local models consume CPU/RAM and have cold-load
latency; Groq consumes network/provider quota and has timeout/rate-limit failure.

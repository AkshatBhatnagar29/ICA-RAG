# Embeddings from first principles

An embedding maps text to a fixed vector. In ICIA, the pipeline is:

```text
text -> E5 tokenizer/ONNX model -> mean pooled normalized representation
     -> 384 floating-point values -> pgvector cosine distance
```

`app/services/indexing/embeddings.py:LocalE5EmbeddingProvider` lazily loads
FastEmbed `intfloat/multilingual-e5-small`, CPU-only, from
`embedding_cache_path`. Documents receive `passage: ` and queries receive
`query: ` prefixes. Batch size and threads are settings. Vector length and
finite values are validated; model/inference errors become explicit failures.

Cosine similarity is the dot product after normalization:

`cos(x,y) = (x dot y) / (||x|| ||y||)`.

The query and document prefixes tell E5 which side of the retrieval task a
string represents. A 384D vector is a quality/CPU/memory compromise, not legal
reasoning. Indexing reuses vectors by content hash and embedding configuration
hash; stable chunk UUIDs make ties reproducible.

FastEmbed supplies ONNX CPU inference and local model caching. It avoids sending
contract text to an embedding API, but consumes local RAM/CPU and has cold-load
latency. Larger E5 models may improve quality but increase memory/latency;
BERT/sentence-transformer APIs would add deployment or service cost.

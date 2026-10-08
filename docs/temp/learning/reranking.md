# Cross-encoder reranking

Dense retrieval encodes query and chunk independently, making large-scale
candidate search cheap. A cross-encoder reads `(query, chunk)` together and can
model fine-grained relevance, but is too expensive to run over the entire
corpus. ICIA therefore uses:

```text
hybrid candidate pool -> (query, chunk) -> Jina cross-encoder score
                       -> deterministic reorder -> generation selection
```

`LocalCrossEncoderReranker` lazily loads
`jinaai/jina-reranker-v1-tiny-en` through FastEmbed ONNX, CPU-only, with cache,
batch size, max length, and thread settings. It deduplicates by chunk UUID,
rejects empty text/non-finite scores, truncates input to candidate limit, and
sorts by score then UUID. It cannot retrieve a chunk absent from its input.

The frozen reranker experiment compares current Jina, `Xenova/ms-marco-MiniLM-
L-6-v2`, and a Jina turbo variant over identical 40-candidate sets. Reports say
MiniLM leads quality on the cached benchmark, turbo regresses, and matched
repeated latency/resource evidence is unresolved; production remains Jina.
These scripts do not change runtime defaults.

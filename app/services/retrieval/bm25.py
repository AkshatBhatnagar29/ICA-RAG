from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence

from app.services.retrieval.models import ChunkMetadata, SparseResult

# Keep legal identifiers and numeric phrases as tokens. Punctuation that carries
# identifier meaning is retained in the same token (for example 12.3(a)).
_TOKEN_RE = re.compile(r"(?:\d+(?:\.\d+)+(?:\([a-zA-Z0-9]+\))?|[a-zA-Z]+(?:[-'][a-zA-Z]+)*|\d+|[\u0900-\u097f]+)", re.UNICODE)


def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold()
    return _TOKEN_RE.findall(text)


class LocalBM25:
    """Deterministic BM25 over the authorized chunk set.

    This intentionally does not build a persistent inverted index in Phase 5.
    At larger corpus sizes, measured latency and memory should drive a future
    PostgreSQL FTS or dedicated sparse-index decision.
    """

    def __init__(self, k1: float = 1.2, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

    def search(self, query: str, chunks: Sequence[ChunkMetadata], top_k: int) -> list[SparseResult]:
        query_terms = tokenize(query)
        if not query_terms or not chunks:
            return []
        documents = [tokenize(chunk.text) for chunk in chunks]
        avgdl = sum(len(doc) for doc in documents) / len(documents)
        document_frequency: Counter[str] = Counter()
        for doc in documents:
            document_frequency.update(set(doc))
        scored: list[tuple[float, ChunkMetadata]] = []
        for chunk, doc in zip(chunks, documents, strict=True):
            frequencies = Counter(doc)
            score = 0.0
            for term in query_terms:
                if not frequencies[term]:
                    continue
                df = document_frequency[term]
                idf = math.log(1.0 + (len(documents) - df + 0.5) / (df + 0.5))
                denominator = frequencies[term] + self.k1 * (1.0 - self.b + self.b * len(doc) / avgdl)
                score += idf * frequencies[term] * (self.k1 + 1.0) / denominator
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], str(item[1].chunk_id)))
        return [SparseResult(metadata=chunk, score=score, rank=rank)
                for rank, (score, chunk) in enumerate(scored[:top_k], start=1)]

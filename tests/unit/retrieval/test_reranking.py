from __future__ import annotations

import uuid

import pytest

from app.core.config import Settings
from app.services.reranking.service import LocalCrossEncoderReranker, RerankingError
from app.services.retrieval.models import ChunkMetadata, HybridResult


def candidate(text: str, rank: int = 1) -> HybridResult:
    metadata = ChunkMetadata(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), text, 1, 1, "1", "7", "Termination",
        "7.1", "Notice", "CLAUSE", "PDF", [],
    )
    return HybridResult(metadata=metadata, rrf_score=1 / rank, original_rrf_rank=rank, final_rank=rank)


class FakeEncoder:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.calls: list[tuple[str, list[str], int, int]] = []

    def rerank(self, query: str, documents: list[str], batch_size: int, max_length: int) -> list[float]:
        self.calls.append((query, documents, batch_size, max_length))
        return self.scores


def reranker(candidate_limit: int = 40) -> LocalCrossEncoderReranker:
    settings = Settings(
        reranker_candidate_k=candidate_limit, reranker_batch_size=2, reranker_max_length=256,
    )
    return LocalCrossEncoderReranker(settings)


def test_empty_candidates_do_not_load_model() -> None:
    instance = reranker()
    assert instance.rerank("notice period", []) == []
    assert instance._encoder is None


def test_batch_scores_are_applied_with_stable_tie_breaking() -> None:
    instance = reranker()
    first, second = candidate("first", 1), candidate("second", 2)
    fake = FakeEncoder([0.5, 0.5])
    instance._encoder = fake

    result = instance.rerank("notice period", [second, first])

    assert [item.result.metadata.text for item in result] == [
        item.metadata.text for item in sorted([second, first], key=lambda x: str(x.metadata.chunk_id))
    ]
    assert fake.calls == [("notice period", ["second", "first"], 2, 256)]
    expected = sorted([second, first], key=lambda x: str(x.metadata.chunk_id))
    assert [item.original_rank for item in result] == [item.original_rrf_rank for item in expected]


def test_duplicates_and_maximum_candidate_limit_are_enforced() -> None:
    instance = reranker(candidate_limit=2)
    first, second, third = candidate("first"), candidate("second", 2), candidate("third", 3)
    fake = FakeEncoder([3.0, 1.0])
    instance._encoder = fake

    result = instance.rerank("query", [first, first, second, third])

    assert len(result) == 2
    assert fake.calls[0][1] == ["first", "second"]


def test_malformed_candidate_fails_explicitly() -> None:
    instance = reranker()
    malformed = candidate(" ")
    with pytest.raises(RerankingError, match="malformed"):
        instance.rerank("query", [malformed])

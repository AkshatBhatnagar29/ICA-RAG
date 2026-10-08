from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.services.retrieval.models import HybridResult


@dataclass(frozen=True)
class RerankedResult:
    """A retrieval candidate with its independent cross-encoder score."""

    result: HybridResult
    score: float
    original_rank: int
    final_rank: int


class Reranker(Protocol):
    model: str
    model_version: str
    batch_size: int
    max_length: int
    candidate_limit: int

    def rerank(self, query: str, candidates: Sequence[HybridResult]) -> list[RerankedResult]: ...

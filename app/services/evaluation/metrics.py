from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    expected = set(relevant)
    return len(set(retrieved[:k]) & expected) / len(expected) if expected else 0.0


def precision_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    if k < 1:
        raise ValueError("k must be positive")
    expected = set(relevant)
    return sum(item in expected for item in retrieved[:k]) / k if expected else 0.0


def reciprocal_rank(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    expected = set(relevant)
    return next((1.0 / rank for rank, item in enumerate(retrieved, 1) if item in expected), 0.0)


def ndcg_at_k(retrieved: Sequence[str], relevance: dict[str, float], k: int) -> float:
    def dcg(values: Sequence[float]) -> float:
        return sum(value / math.log2(rank + 2) for rank, value in enumerate(values))
    actual = dcg([relevance.get(item, 0.0) for item in retrieved[:k]])
    ideal = dcg(sorted(relevance.values(), reverse=True)[:k])
    return actual / ideal if ideal else 0.0


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def percentile(values: Sequence[float], percentile_value: float) -> float:
    if not values or not 0 <= percentile_value <= 100:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value / 100
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def citation_precision(citations: Sequence[str], available: Iterable[str]) -> float:
    valid = set(available)
    return sum(citation in valid for citation in citations) / len(citations) if citations else 0.0


def citation_recall(citations: Sequence[str], expected: Iterable[str]) -> float:
    expected_set = set(expected)
    return len(set(citations) & expected_set) / len(expected_set) if expected_set else 0.0


def unsupported_claim_rate(supported: Sequence[bool]) -> float:
    return 1.0 - mean([1.0 if item else 0.0 for item in supported]) if supported else 0.0


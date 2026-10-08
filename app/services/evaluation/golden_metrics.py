"""Deterministic scoring helpers for the end-to-end golden evaluation."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from typing import Any


def _text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def evidence_matches(item: dict[str, Any], expected: dict[str, Any]) -> bool:
    anchor = _text(expected.get("anchor"))
    haystack = _text(" ".join(str(item.get(key, "")) for key in (
        "text", "source_identifier", "source_citation", "section", "clause", "chunk_id")))
    page = expected.get("page")
    page_matches = page is None or page in (item.get("page_start"), item.get("page_end"))
    return bool(anchor and anchor in haystack and page_matches)


def expected_evidence_found(results: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]) -> bool:
    return not expected or all(any(evidence_matches(item, target) for item in results) for target in expected)


def first_relevant_rank(results: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]) -> int | None:
    for rank, item in enumerate(results, 1):
        if any(evidence_matches(item, target) for target in expected):
            return rank
    return None


def recall_at_k(results: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]], k: int) -> float:
    if not expected:
        return 1.0
    return sum(any(evidence_matches(item, target) for item in results[:k]) for target in expected) / len(expected)


def reciprocal_rank(results: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]) -> float:
    rank = first_relevant_rank(results, expected)
    return 1.0 / rank if rank else 0.0


def ndcg_at_k(results: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]], k: int) -> float:
    def relevance(item: dict[str, Any]) -> float:
        return 1.0 if any(evidence_matches(item, target) for target in expected) else 0.0
    actual = sum(relevance(item) / math.log2(rank + 1)
                 for rank, item in enumerate(results[:k], 1))
    ideal = sum(1.0 / math.log2(rank + 1)
                for rank in range(1, min(len(expected), k) + 1))
    return actual / ideal if ideal else 0.0


def forbidden_claims(answer: str, forbidden: Iterable[str]) -> list[str]:
    normalized = _text(answer)
    return [claim for claim in forbidden if _text(claim) and _text(claim) in normalized]


def concept_coverage(answer: str, concepts: Iterable[str]) -> float:
    values = list(concepts)
    normalized_answer = _text(answer)
    return sum(_concept_present(normalized_answer, concept) for concept in values) / len(values) if values else 1.0


def _concept_present(answer: str, concept: str) -> bool:
    expected = _text(concept)
    if expected in answer:
        return True
    alternatives = {
        "written notice": ("notice in writing",),
        "one month's advance notice": ("one month's advance written notice",),
    }
    if any(_text(value) in answer for value in alternatives.get(expected, ())):
        return True
    variants = {
        "completion": "complete",
        "obligations": "obligation",
        "documents": "document",
        "provisions": "provision",
    }
    words = [variants.get(word, word) for word in re.findall(r"[a-z0-9]+", expected)]
    if not words:
        return False
    answer_words = set(re.findall(r"[a-z0-9]+", answer))
    return all(word in answer_words for word in words)


def citation_scores(citations: Sequence[str], evidence: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]) -> dict[str, float | int]:
    registry = {str(item.get("evidence_id")): item for item in evidence}
    valid = [citation for citation in citations if citation in registry]
    relevant = sum(any(evidence_matches(registry[citation], target) for target in expected) for citation in valid)
    return {
        "count": len(citations),
        "coverage": relevant / len(expected) if expected else (1.0 if citations or not expected else 0.0),
        "correctness": relevant / len(valid) if valid else 0.0,
        "presence": 1.0 if citations else 0.0,
        "unsupported": (len(citations) - relevant) / len(citations) if citations else 0.0,
    }


def limitation_present(answer: str) -> bool:
    normalized = _text(answer)
    return any(marker in normalized for marker in (
        "cannot be determined", "not provided", "not identified", "insufficient", "unable to determine",
        "not enough evidence", "unavailable", "does not contain",
    ))

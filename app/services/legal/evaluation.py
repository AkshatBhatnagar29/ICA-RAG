from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from app.services.legal.models import LegalAnalysis, LegalEvidence


def recall_at_k(retrieved_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    return len(set(retrieved_ids[:k]) & relevant) / len(relevant)


def mean_reciprocal_rank(retrieved_ids: Sequence[str], relevant_ids: Iterable[str]) -> float:
    relevant = set(relevant_ids)
    return next((1.0 / rank for rank, item in enumerate(retrieved_ids, 1) if item in relevant), 0.0)


def ndcg_at_k(retrieved_ids: Sequence[str], relevance: dict[str, float], k: int) -> float:
    def dcg(values: Sequence[float]) -> float:
        return sum(value / math.log2(rank + 2) for rank, value in enumerate(values))
    actual = dcg([relevance.get(item, 0.0) for item in retrieved_ids[:k]])
    ideal = dcg(sorted(relevance.values(), reverse=True)[:k])
    return actual / ideal if ideal else 0.0


def citation_correctness(analysis: LegalAnalysis, evidence: Sequence[LegalEvidence]) -> float:
    registry = {item.evidence_id: item for item in evidence}
    if not analysis.citations:
        return 0.0
    valid = sum(1 for citation in analysis.citations if citation.evidence_id in registry)
    return valid / len(analysis.citations)


def unsupported_claim_rate(analysis: LegalAnalysis, evidence: Sequence[LegalEvidence], claims: Sequence[str]) -> float:
    """A small deterministic baseline: claims must explicitly cite retrieved IDs."""
    if not claims:
        return 0.0
    cited = {citation.evidence_id for citation in analysis.citations}
    valid = {item.evidence_id for item in evidence}
    supported = bool(cited & valid)
    return 0.0 if supported else 1.0

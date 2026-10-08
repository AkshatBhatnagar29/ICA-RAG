from __future__ import annotations

from collections.abc import Sequence

from app.services.retrieval.models import DenseResult, HybridResult, SparseResult


def reciprocal_rank_fusion(
    dense: Sequence[DenseResult], sparse: Sequence[SparseResult], top_k: int, rrf_k: int = 60,
    dense_weight: float = 1.0, sparse_weight: float = 1.0,
) -> list[HybridResult]:
    if rrf_k < 1:
        raise ValueError("rrf_k must be positive")
    if dense_weight < 0 or sparse_weight < 0 or dense_weight == sparse_weight == 0:
        raise ValueError("fusion weights must be non-negative and not both zero")
    merged: dict[str, HybridResult] = {}
    for dense_item in dense:
        key = str(dense_item.metadata.chunk_id)
        result: HybridResult = merged.setdefault(key, HybridResult(metadata=dense_item.metadata))
        result.dense_rank = dense_item.rank
        result.dense_score = dense_item.score
        result.rrf_score += dense_weight / (rrf_k + dense_item.rank)
    for sparse_item in sparse:
        key = str(sparse_item.metadata.chunk_id)
        sparse_result: HybridResult = merged.setdefault(key, HybridResult(metadata=sparse_item.metadata))
        sparse_result.sparse_rank = sparse_item.rank
        sparse_result.sparse_score = sparse_item.score
        sparse_result.rrf_score += sparse_weight / (rrf_k + sparse_item.rank)
    ordered = sorted(merged.values(), key=lambda item: (-item.rrf_score, str(item.metadata.chunk_id)))
    for rank, fused_item in enumerate(ordered[:top_k], start=1):
        fused_item.original_rrf_rank = rank
        fused_item.final_rank = rank
    return ordered[:top_k]

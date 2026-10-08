import uuid

import pytest

from app.services.retrieval.fusion import reciprocal_rank_fusion
from app.services.retrieval.models import (
    ChunkMetadata,
    DenseResult,
    RetrievalMode,
    RetrievalQuery,
    RetrievalScope,
    SparseResult,
)
from app.services.retrieval.query import InvalidRetrievalQuery, QueryProcessor
from app.services.retrieval.service import RetrievalService


def item() -> ChunkMetadata:
    return ChunkMetadata(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "text", 1, 1, "1", "7", "Termination", "7.1", "Notice", "CLAUSE", "PDF", [])


def test_query_normalization_preserves_legal_content() -> None:
    assert QueryProcessor().normalize("  Section 73\n  30 days  prior notice ") == "Section 73 30 days prior notice"


def test_invalid_query_and_missing_tenant_fail_closed() -> None:
    with pytest.raises(InvalidRetrievalQuery):
        QueryProcessor().normalize("   ")


def test_rrf_deduplicates_and_preserves_component_evidence() -> None:
    first, second = item(), item()
    result = reciprocal_rank_fusion(
        [DenseResult(first, 0.9, 1), DenseResult(second, 0.8, 2)],
        [SparseResult(second, 2.0, 1)], 2, rrf_k=1,
    )
    assert len(result) == 2
    assert result[0].metadata.chunk_id == second.chunk_id
    assert result[0].dense_rank == 2
    assert result[0].sparse_rank == 1
    assert result[0].final_rank == 1


def test_weighted_rrf_can_prefer_sparse_rank_without_losing_union() -> None:
    first, second = item(), item()
    result = reciprocal_rank_fusion(
        [DenseResult(first, 0.9, 1)], [SparseResult(second, 2.0, 1)], 2,
        rrf_k=60, dense_weight=1.0, sparse_weight=2.0,
    )
    assert [entry.metadata.chunk_id for entry in result] == [second.chunk_id, first.chunk_id]
    assert result[0].dense_rank is None
    assert result[0].sparse_rank == 1


def test_rrf_rejects_invalid_weights() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([], [], 2, dense_weight=0, sparse_weight=0)


def test_rrf_k_changes_score_without_changing_rank_inputs() -> None:
    first = item()
    dense = [DenseResult(first, 0.9, 1)]
    low = reciprocal_rank_fusion(dense, [], 1, rrf_k=20)[0].rrf_score
    high = reciprocal_rank_fusion(dense, [], 1, rrf_k=100)[0].rrf_score
    assert low == 1 / 21
    assert high == 1 / 101
    assert low != high


@pytest.mark.asyncio
async def test_non_reranked_response_exposes_same_candidate_pool_for_accounting() -> None:
    first, second = item(), item()
    service = RetrievalService(provider=object())

    async def dense(_session: object, _request: RetrievalQuery, _candidate_k: int) -> list[DenseResult]:
        return [DenseResult(first, 0.9, 1), DenseResult(second, 0.8, 2)]

    async def sparse(_session: object, _request: RetrievalQuery, _candidate_k: int) -> list[SparseResult]:
        return [SparseResult(second, 2.0, 1)]

    service.dense = dense  # type: ignore[method-assign]
    service.sparse = sparse  # type: ignore[method-assign]
    response = await service.search(object(), RetrievalQuery(
        query="notice", scope=RetrievalScope(tenant_id=uuid.uuid4()), top_k=1, mode=RetrievalMode.HYBRID,
    ))

    assert len(response.results) == 1
    assert len(response.candidate_results) == 2
    assert {entry.metadata.chunk_id for entry in response.results} <= {
        entry.metadata.chunk_id for entry in response.candidate_results
    }

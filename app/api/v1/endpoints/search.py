from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.retrieval import SearchDiagnostics, SearchRequest, SearchResponse, SearchResult
from app.security.auth import REQUIRE_SEARCH_READ, AuthContext
from app.services.reranking.service import RerankingError
from app.services.retrieval.models import RetrievalQuery, RetrievalScope
from app.services.retrieval.query import InvalidRetrievalQuery
from app.services.retrieval.service import RetrievalService

router = APIRouter(prefix="/search", tags=["retrieval"])
DB_SESSION = Depends(get_db_session)


@router.post("", response_model=SearchResponse)
async def search(
    payload: SearchRequest, request: Request, session: AsyncSession = DB_SESSION,
    context: AuthContext = REQUIRE_SEARCH_READ
) -> SearchResponse:
    query = RetrievalQuery(
        query=payload.query,
        scope=RetrievalScope.model_validate({**payload.scope.model_dump(), "tenant_id": context.tenant.id}),
        top_k=payload.top_k,
        mode=payload.mode,
        rerank=payload.rerank,
    )
    service: RetrievalService = request.app.state.retrieval_service
    try:
        response = await service.search(session, query)
    except InvalidRetrievalQuery as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RerankingError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return SearchResponse(
        results=[SearchResult(
            **result.metadata.__dict__, dense_rank=result.dense_rank, dense_score=result.dense_score,
            sparse_rank=result.sparse_rank, sparse_score=result.sparse_score,
            rrf_score=result.rrf_score, reranker_score=result.reranker_score,
            original_rrf_rank=result.original_rrf_rank, final_rank=result.final_rank,
        ) for result in response.results],
        diagnostics=SearchDiagnostics(
            mode=response.diagnostics.mode, requested_top_k=response.diagnostics.requested_top_k,
            dense_candidate_count=response.diagnostics.dense_candidate_count,
            sparse_candidate_count=response.diagnostics.sparse_candidate_count,
            fused_candidate_count=response.diagnostics.fused_candidate_count,
            result_count=response.diagnostics.result_count, latency_ms=response.diagnostics.latency_ms,
            scope=payload.scope, errors=response.diagnostics.errors,
            reranker_enabled=response.diagnostics.reranker_enabled,
            reranker_model=response.diagnostics.reranker_model,
            reranker_candidate_count=response.diagnostics.reranker_candidate_count,
            reranker_final_count=response.diagnostics.reranker_final_count,
            reranker_latency_ms=response.diagnostics.reranker_latency_ms,
            reranker_batch_size=response.diagnostics.reranker_batch_size,
        ),
    )

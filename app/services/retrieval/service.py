from __future__ import annotations

import time
from typing import Any, cast

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.observability.metrics import metrics
from app.services.indexing.embeddings import EmbeddingProvider
from app.services.reranking.models import Reranker
from app.services.reranking.service import RerankingError
from app.services.retrieval.bm25 import LocalBM25
from app.services.retrieval.fusion import reciprocal_rank_fusion
from app.services.retrieval.models import (
    ChunkMetadata,
    DenseResult,
    HybridResult,
    RetrievalDiagnostics,
    RetrievalMode,
    RetrievalQuery,
    RetrievalResponse,
    SparseResult,
)
from app.services.retrieval.query import QueryProcessor


def _metadata(chunk: Chunk) -> ChunkMetadata:
    return ChunkMetadata(
        chunk_id=chunk.id, document_id=chunk.document_id, document_version_id=chunk.document_version_id,
        text=chunk.text, physical_page_start=chunk.physical_page_start,
        physical_page_end=chunk.physical_page_end, printed_page_label=chunk.printed_page_label,
        section_identifier=chunk.section_identifier, section_title=chunk.section_title,
        clause_number=chunk.clause_number, clause_title=chunk.clause_title,
        chunk_type=chunk.chunk_type.value if hasattr(chunk.chunk_type, "value") else str(chunk.chunk_type),
        extraction_method=chunk.extraction_method,
        source_block_provenance=chunk.source_block_provenance,
        tenant_id=chunk.tenant_id,
    )


class RetrievalService:
    def __init__(self, provider: EmbeddingProvider | None = None, rrf_k: int = 60,
                 reranker: Reranker | None = None, dense_weight: float = 1.0,
                 sparse_weight: float = 1.0) -> None:
        self.provider = provider
        self.query_processor = QueryProcessor()
        self.bm25 = LocalBM25()
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.reranker = reranker

    def _scope_query(self, query: Select[tuple[Chunk]], request: RetrievalQuery) -> Select[tuple[Chunk]]:
        scope = request.scope
        if scope.tenant_id is None:
            raise PermissionError("tenant scope is required for retrieval")
        statement = query.where(Chunk.tenant_id == scope.tenant_id)
        if scope.document_id is not None:
            statement = statement.where(Chunk.document_id == scope.document_id)
        if scope.document_version_id is not None:
            statement = statement.where(Chunk.document_version_id == scope.document_version_id)
        if scope.filters is not None:
            filters = scope.filters
            if filters.section_identifier is not None:
                statement = statement.where(Chunk.section_identifier == filters.section_identifier)
            if filters.clause_number is not None:
                statement = statement.where(Chunk.clause_number == filters.clause_number)
            if filters.chunk_type is not None:
                statement = statement.where(Chunk.chunk_type == filters.chunk_type)
        return statement

    async def _authorized_chunks(self, session: AsyncSession, request: RetrievalQuery) -> list[Chunk]:
        result = await session.execute(self._scope_query(select(Chunk), request).order_by(Chunk.id.asc()))
        return list(result.scalars().all())

    async def dense(self, session: AsyncSession, request: RetrievalQuery, candidate_k: int) -> list[DenseResult]:
        started = time.perf_counter()
        provider = self.provider
        if provider is None:
            raise RuntimeError("RetrievalService requires an embedding provider for dense retrieval")
        vector = provider.embed_query(request.query)
        distance = Chunk.embedding.cosine_distance(vector).label("distance")
        result = await session.execute(
            self._scope_query(select(Chunk, distance), request)
            .order_by(distance.asc(), Chunk.id.asc()).limit(candidate_k)
        )
        rows = cast(list[tuple[Chunk, Any]], result.all())
        output = [DenseResult(metadata=_metadata(chunk), score=1.0 - float(distance_value), rank=rank)
                for rank, (chunk, distance_value) in enumerate(rows, start=1)]
        metrics.observe("retrieval_dense_latency_ms", (time.perf_counter() - started) * 1000)
        return output

    async def sparse(self, session: AsyncSession, request: RetrievalQuery, candidate_k: int) -> list[SparseResult]:
        started = time.perf_counter()
        chunks = await self._authorized_chunks(session, request)
        output = self.bm25.search(request.query, [_metadata(chunk) for chunk in chunks], candidate_k)
        metrics.observe("retrieval_bm25_latency_ms", (time.perf_counter() - started) * 1000)
        return output

    async def search(self, session: AsyncSession, request: RetrievalQuery) -> RetrievalResponse:
        started = time.perf_counter()
        request.query = self.query_processor.normalize(request.query)
        self.query_processor.validate_scope(request.scope)
        candidate_k = max(request.top_k, request.top_k * 5)
        if request.rerank and self.reranker is not None:
            candidate_k = max(request.top_k, self.reranker.candidate_limit)
        dense: list[DenseResult] = []
        sparse: list[SparseResult] = []
        diagnostics = RetrievalDiagnostics(mode=request.mode, requested_top_k=request.top_k, scope=request.scope)
        if request.mode in (RetrievalMode.DENSE, RetrievalMode.HYBRID):
            dense = await self.dense(session, request, candidate_k)
        if request.mode in (RetrievalMode.SPARSE, RetrievalMode.HYBRID):
            sparse = await self.sparse(session, request, candidate_k)
        # Always retain the full candidate pool for diagnostics and evaluation;
        # only the exposed result list is truncated when reranking is disabled.
        result_limit = candidate_k
        if request.mode == RetrievalMode.DENSE:
            results = [HybridResult(metadata=item.metadata, dense_rank=item.rank, dense_score=item.score,
                                    rrf_score=item.score, original_rrf_rank=item.rank,
                                    final_rank=item.rank) for item in dense[:result_limit]]
        elif request.mode == RetrievalMode.SPARSE:
            results = [HybridResult(metadata=item.metadata, sparse_rank=item.rank, sparse_score=item.score,
                                    rrf_score=item.score, original_rrf_rank=item.rank,
                                    final_rank=item.rank) for item in sparse[:result_limit]]
        else:
            fusion_started = time.perf_counter()
            results = reciprocal_rank_fusion(dense, sparse, result_limit, self.rrf_k,
                                             self.dense_weight, self.sparse_weight)
            metrics.observe("retrieval_rrf_latency_ms", (time.perf_counter() - fusion_started) * 1000)
        candidate_results = list(results)
        if not request.rerank:
            results = results[:request.top_k]
        diagnostics.dense_candidate_count = len(dense)
        diagnostics.sparse_candidate_count = len(sparse)
        dense_ids = {str(item.metadata.chunk_id) for item in dense}
        sparse_ids = {str(item.metadata.chunk_id) for item in sparse}
        diagnostics.fused_candidate_count = len(dense_ids | sparse_ids)
        metrics.observe("retrieval_candidate_count", diagnostics.fused_candidate_count)
        if request.rerank:
            if self.reranker is None:
                raise RerankingError("Reranking was requested but no reranker is configured")
            rerank_started = time.perf_counter()
            try:
                reranked = self.reranker.rerank(request.query, results)
            except RerankingError:
                metrics.increment("reranker_failures_total")
                raise
            results = []
            for ranked_item in reranked[:request.top_k]:
                ranked_item.result.reranker_score = ranked_item.score
                ranked_item.result.original_rrf_rank = ranked_item.original_rank
                ranked_item.result.final_rank = ranked_item.final_rank
                results.append(ranked_item.result)
            diagnostics.reranker_enabled = True
            diagnostics.reranker_model = self.reranker.model
            diagnostics.reranker_candidate_count = len(reranked)
            diagnostics.reranker_final_count = len(results)
            diagnostics.reranker_latency_ms = (time.perf_counter() - rerank_started) * 1000
            diagnostics.reranker_batch_size = self.reranker.batch_size
            metrics.observe("reranker_latency_ms", diagnostics.reranker_latency_ms or 0.0)
            metrics.observe("reranker_candidate_count", len(reranked))
        else:
            for item in results:
                item.original_rrf_rank = item.original_rrf_rank or item.final_rank
                item.reranker_score = None
        diagnostics.result_count = len(results)
        diagnostics.latency_ms = (time.perf_counter() - started) * 1000
        return RetrievalResponse(results=results, diagnostics=diagnostics, candidate_results=candidate_results)

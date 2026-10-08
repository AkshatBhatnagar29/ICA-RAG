from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.services.retrieval.models import RetrievalFilter, RetrievalMode


class RetrievalScopeRequest(BaseModel):
    tenant_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    document_version_id: uuid.UUID | None = None
    filters: RetrievalFilter | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    scope: RetrievalScopeRequest
    top_k: int = Field(default=10, ge=1, le=100)
    mode: RetrievalMode = RetrievalMode.HYBRID
    rerank: bool = False


class SearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    text: str
    physical_page_start: int | None
    physical_page_end: int | None
    printed_page_label: str | None
    section_identifier: str | None
    section_title: str | None
    clause_number: str | None
    clause_title: str | None
    chunk_type: str
    extraction_method: str
    source_block_provenance: list[dict[str, Any]]
    dense_rank: int | None
    dense_score: float | None
    sparse_rank: int | None
    sparse_score: float | None
    rrf_score: float
    reranker_score: float | None
    original_rrf_rank: int | None
    final_rank: int


class SearchDiagnostics(BaseModel):
    mode: RetrievalMode
    requested_top_k: int
    dense_candidate_count: int
    sparse_candidate_count: int
    fused_candidate_count: int
    result_count: int
    latency_ms: float
    scope: RetrievalScopeRequest | None
    errors: list[str]
    reranker_enabled: bool
    reranker_model: str | None
    reranker_candidate_count: int
    reranker_final_count: int
    reranker_latency_ms: float | None
    reranker_batch_size: int | None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    diagnostics: SearchDiagnostics

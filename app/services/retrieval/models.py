from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RetrievalMode(str, enum.Enum):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


class RetrievalFilter(BaseModel):
    section_identifier: str | None = None
    clause_number: str | None = None
    chunk_type: str | None = None


class RetrievalScope(BaseModel):
    tenant_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    document_version_id: uuid.UUID | None = None
    filters: RetrievalFilter | None = None


class RetrievalQuery(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    scope: RetrievalScope
    top_k: int = Field(default=10, ge=1, le=100)
    mode: RetrievalMode = RetrievalMode.HYBRID
    rerank: bool = False

    @model_validator(mode="after")
    def require_tenant_scope(self) -> RetrievalQuery:
        if self.scope.tenant_id is None:
            raise ValueError("tenant_id is required for retrieval")
        return self


@dataclass(frozen=True)
class ChunkMetadata:
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
    tenant_id: uuid.UUID | None = None
    corpus: str = "contract"
    source_type: str | None = None
    source_citation: str | None = None
    corpus_version_id: uuid.UUID | None = None
    legal_document_version_id: uuid.UUID | None = None
    subsection_identifier: str | None = None
    paragraph_identifier: str | None = None


@dataclass(frozen=True)
class DenseResult:
    metadata: ChunkMetadata
    score: float
    rank: int


@dataclass(frozen=True)
class SparseResult:
    metadata: ChunkMetadata
    score: float
    rank: int


@dataclass
class HybridResult:
    metadata: ChunkMetadata
    dense_rank: int | None = None
    dense_score: float | None = None
    sparse_rank: int | None = None
    sparse_score: float | None = None
    rrf_score: float = 0.0
    reranker_score: float | None = None
    original_rrf_rank: int | None = None
    final_rank: int = 0


@dataclass
class RetrievalDiagnostics:
    mode: RetrievalMode
    requested_top_k: int
    dense_candidate_count: int = 0
    sparse_candidate_count: int = 0
    fused_candidate_count: int = 0
    result_count: int = 0
    latency_ms: float = 0.0
    scope: RetrievalScope | None = None
    errors: list[str] = field(default_factory=list)
    reranker_enabled: bool = False
    reranker_model: str | None = None
    reranker_candidate_count: int = 0
    reranker_final_count: int = 0
    reranker_latency_ms: float | None = None
    reranker_batch_size: int | None = None


@dataclass
class RetrievalResponse:
    results: list[HybridResult]
    diagnostics: RetrievalDiagnostics
    candidate_results: list[HybridResult] = field(default_factory=list)

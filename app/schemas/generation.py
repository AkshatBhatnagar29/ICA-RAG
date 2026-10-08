from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.services.retrieval.models import RetrievalMode


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    tenant_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    document_version_id: uuid.UUID | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    mode: RetrievalMode = RetrievalMode.HYBRID
    rerank: bool = False


class ChatCitation(BaseModel):
    citation_id: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    page_start: int | None
    page_end: int | None
    section_identifier: str | None
    section_title: str | None
    clause_identifier: str | None


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation]
    limitations: str | None = None
    retrieval: dict[str, int | bool]

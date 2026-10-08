from __future__ import annotations

import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class LegalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)
    deterministic_text: str = Field(min_length=1, max_length=4000)
    semantic_expansion: str | None = None
    tenant_id: uuid.UUID
    corpus_version_id: uuid.UUID
    top_k: int = Field(default=10, ge=1, le=100)


@dataclass(frozen=True)
class LegalEvidence:
    evidence_id: str
    legal_chunk_id: uuid.UUID
    legal_document_version_id: uuid.UUID
    corpus_version_id: uuid.UUID
    text: str
    source_type: str
    source_citation: str | None
    title: str
    section_identifier: str | None
    subsection_identifier: str | None
    article_identifier: str | None
    paragraph_identifier: str | None
    physical_page_start: int | None
    physical_page_end: int | None
    source_provenance: list[dict[str, object]]


class LegalEvidenceGate(BaseModel):
    sufficient: bool
    reason: str
    evidence_count: int


class LegalCitation(BaseModel):
    evidence_id: str
    source_citation: str | None = None
    quote: str | None = None


class LegalAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    citations: list[LegalCitation] = Field(default_factory=list)
    evidence_gate: LegalEvidenceGate

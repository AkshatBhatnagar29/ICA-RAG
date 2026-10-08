"""Versioned schema and validation helpers for golden RAG datasets."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GoldenCategory = Literal[
    "contract_factual",
    "obligation",
    "payment_financial",
    "termination_notice",
    "renewal_condition_exception",
    "scope_of_work",
    "service_level",
    "penalty_or_deduction",
    "indemnity_or_liability",
    "confidentiality_or_data",
    "dispute_resolution",
    "governing_law_or_jurisdiction",
    "indemnity_liability_confidentiality_ip",
    "dispute_precedence",
    "risk_analysis",
    "insufficient_evidence",
    "legal_scope_required",
    "mixed_contract_legal",
    "citation_integrity",
]
EvidenceMode = Literal["ANY_OF", "ALL_OF", "MINIMUM_N"]


class GoldenEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int | None = Field(default=None, ge=1)
    anchor: str | None = Field(default=None, min_length=1)
    chunk_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def has_locator(self) -> GoldenEvidence:
        if self.anchor is None and self.chunk_id is None:
            raise ValueError("evidence must contain an anchor or chunk_id")
        return self


class GoldenEvidenceGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: EvidenceMode
    targets: list[GoldenEvidence] = Field(min_length=1)
    minimum_n: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def valid_minimum(self) -> GoldenEvidenceGroup:
        if self.mode == "MINIMUM_N" and (self.minimum_n is None or self.minimum_n > len(self.targets)):
            raise ValueError("MINIMUM_N requires 1 <= minimum_n <= number of targets")
        if self.mode != "MINIMUM_N" and self.minimum_n is not None:
            raise ValueError("minimum_n is only valid for MINIMUM_N")
        return self


class GoldenDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_version_id: uuid.UUID
    source_document: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: str = Field(min_length=1)


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: str = Field(min_length=1, pattern=r"^[A-Z0-9][A-Z0-9_-]+$")
    category: GoldenCategory
    question: str = Field(min_length=10)
    document_version_id: uuid.UUID
    requires_contract: bool = True
    requires_legal: bool = False
    legal_corpus_version_id: uuid.UUID | None = None
    difficulty: Literal["easy", "moderate", "hard", "adversarial"] = "moderate"
    expected_concepts: list[str] = Field(default_factory=list)
    expected_answer: str = Field(min_length=1)
    forbidden_claims: list[str] = Field(default_factory=list)
    expected_evidence: list[GoldenEvidence] = Field(default_factory=list)
    evidence_groups: list[GoldenEvidenceGroup] = Field(default_factory=list)
    minimum_citations: int = Field(default=0, ge=0)
    insufficient_evidence_expected: bool = False
    retrieval_applicable: bool = True
    hard_negative_of: list[str] = Field(default_factory=list)
    provenance: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_semantics(self) -> GoldenCase:
        if self.requires_legal and self.legal_corpus_version_id is None:
            raise ValueError("legal cases must identify a legal_corpus_version_id")
        if self.minimum_citations > 0 and not self.requires_legal and not self.expected_evidence:
            raise ValueError("citation requirement has no contract evidence")
        if self.insufficient_evidence_expected and self.expected_evidence and not self.expected_answer:
            raise ValueError("insufficient-evidence case must still have an answer policy")
        if self.category == "insufficient_evidence" and not self.insufficient_evidence_expected:
            raise ValueError("insufficient_evidence category must set insufficient_evidence_expected")
        return self


class GoldenDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_documents: list[GoldenDocument] = Field(min_length=1)
    legal_corpus_versions: list[uuid.UUID] = Field(default_factory=list)
    cases: list[GoldenCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> GoldenDataset:
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate golden case IDs")
        document_ids = {item.document_version_id for item in self.source_documents}
        if any(case.document_version_id not in document_ids for case in self.cases):
            raise ValueError("case references a document version not declared in source_documents")
        legal_ids = set(self.legal_corpus_versions)
        if any(case.legal_corpus_version_id not in legal_ids for case in self.cases if case.legal_corpus_version_id):
            raise ValueError("case references an undeclared legal corpus version")
        return self


def load_golden_dataset(path: Path) -> GoldenDataset:
    return GoldenDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))


def validate_answer_leakage(dataset: GoldenDataset) -> list[str]:
    """Return diagnostics for accidental answer text copied into a question."""
    diagnostics: list[str] = []
    for case in dataset.cases:
        question_words = set(re.findall(r"[a-z0-9]{5,}", case.question.casefold()))
        answer_words = set(re.findall(r"[a-z0-9]{5,}", case.expected_answer.casefold()))
        overlap = question_words & answer_words
        if len(overlap) >= max(6, int(len(answer_words) * 0.75)):
            diagnostics.append(f"{case.id}: question substantially repeats expected answer wording")
    return diagnostics


def legacy_cases(path: Path) -> list[dict[str, Any]]:
    """Load the original v1 list without requiring v2 provenance fields."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [dict(item) for item in payload.get("cases", payload)]

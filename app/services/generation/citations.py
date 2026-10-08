from __future__ import annotations

from dataclasses import dataclass

from app.observability.metrics import metrics
from app.services.generation.context import EvidenceItem, EvidencePacket
from app.services.generation.output import GeneratedAnswer


class CitationValidationError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedCitation:
    citation_id: str
    chunk_id: str
    document_id: str
    document_version_id: str
    page_start: int | None
    page_end: int | None
    section_identifier: str | None
    section_title: str | None
    clause_identifier: str | None
    corpus: str = "contract"
    source_type: str | None = None
    source_citation: str | None = None
    corpus_version_id: str | None = None
    legal_document_version_id: str | None = None
    subsection_identifier: str | None = None
    paragraph_identifier: str | None = None


def verify_citations(response: GeneratedAnswer, evidence: EvidencePacket) -> list[VerifiedCitation]:
    # The full registry is retained for diagnostics, but only evidence sent to
    # the provider is citation-authorized for this generation.
    registry = evidence.selected_registry
    seen: set[str] = set()
    verified: list[VerifiedCitation] = []
    for citation in response.citations:
        if citation.citation_id in seen:
            metrics.increment("citation_validation_failures_total", reason="duplicate")
            raise CitationValidationError("duplicate citation ID")
        item: EvidenceItem | None = registry.get(citation.citation_id)
        if item is None:
            metrics.increment("citation_validation_failures_total", reason="unknown")
            raise CitationValidationError(f"unknown citation ID: {citation.citation_id}")
        seen.add(citation.citation_id)
        verified.append(VerifiedCitation(
            citation_id=item.citation_id, chunk_id=str(item.chunk_id), document_id=str(item.document_id),
            document_version_id=str(item.document_version_id), page_start=item.physical_page_start,
            page_end=item.physical_page_end, section_identifier=item.section_identifier,
            section_title=item.section_title, clause_identifier=item.clause_identifier,
            corpus=item.corpus, source_type=item.source_type, source_citation=item.source_citation,
            corpus_version_id=str(item.corpus_version_id) if item.corpus_version_id else None,
            legal_document_version_id=str(item.legal_document_version_id) if item.legal_document_version_id else None,
            subsection_identifier=item.subsection_identifier, paragraph_identifier=item.paragraph_identifier,
        ))
    return verified

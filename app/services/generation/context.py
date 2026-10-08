from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.services.retrieval.models import HybridResult, RetrievalScope


@dataclass(frozen=True)
class EvidenceItem:
    citation_id: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    text: str
    physical_page_start: int | None
    physical_page_end: int | None
    section_identifier: str | None
    section_title: str | None
    clause_identifier: str | None
    clause_title: str | None
    rank: int
    source_block_provenance: list[dict[str, object]] = field(default_factory=list)
    tenant_id: uuid.UUID | None = None
    corpus: str = "contract"
    source_type: str | None = None
    source_citation: str | None = None
    corpus_version_id: uuid.UUID | None = None
    legal_document_version_id: uuid.UUID | None = None
    subsection_identifier: str | None = None
    paragraph_identifier: str | None = None


@dataclass(frozen=True)
class EvidencePacket:
    items: tuple[EvidenceItem, ...]
    context: str
    candidate_count: int
    truncated_count: int
    registry_items: tuple[EvidenceItem, ...] = ()
    context_token_estimate: int = 0

    @property
    def registry(self) -> dict[str, EvidenceItem]:
        return {item.citation_id: item for item in (self.registry_items or self.items)}

    @property
    def selected_registry(self) -> dict[str, EvidenceItem]:
        return {item.citation_id: item for item in self.items}

    @property
    def selected_evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.citation_id for item in self.items)


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def build_evidence_packet(
    results: list[HybridResult],
    max_context_tokens: int = 6000,
    scope: RetrievalScope | None = None,
    generation_top_k: int = 10,
) -> EvidencePacket:
    """Build a full registry and a separate, bounded generation context."""
    if generation_top_k < 1:
        raise ValueError("generation_top_k must be positive")
    registry_items: list[EvidenceItem] = []
    seen: set[uuid.UUID] = set()
    for result in results:
        metadata = result.metadata
        if metadata.chunk_id in seen:
            continue
        if scope is not None and (
            (scope.tenant_id is not None and metadata.tenant_id != scope.tenant_id)
            or (scope.document_id is not None and metadata.document_id != scope.document_id)
            or (scope.document_version_id is not None and metadata.document_version_id != scope.document_version_id)
        ):
            raise PermissionError("retrieval result falls outside the requested scope")
        if not metadata.text.strip():
            continue
        seen.add(metadata.chunk_id)
        citation_id = f"E{len(registry_items) + 1}"
        registry_items.append(EvidenceItem(
            citation_id=citation_id, chunk_id=metadata.chunk_id,
            document_id=metadata.document_id, document_version_id=metadata.document_version_id,
            text=metadata.text, physical_page_start=metadata.physical_page_start,
            physical_page_end=metadata.physical_page_end, section_identifier=metadata.section_identifier,
            section_title=metadata.section_title, clause_identifier=metadata.clause_number,
            clause_title=metadata.clause_title, rank=result.final_rank,
            source_block_provenance=metadata.source_block_provenance,
            tenant_id=metadata.tenant_id,
            corpus=metadata.corpus, source_type=metadata.source_type,
            source_citation=metadata.source_citation, corpus_version_id=metadata.corpus_version_id,
            legal_document_version_id=metadata.legal_document_version_id,
            subsection_identifier=metadata.subsection_identifier,
            paragraph_identifier=metadata.paragraph_identifier,
        ))
    selected: list[EvidenceItem] = []
    used = 0
    skipped = 0
    for item in registry_items[:generation_top_k]:
        cost = _estimate_tokens(item.text)
        if used + cost > max_context_tokens:
            skipped += 1
            continue
        selected.append(item)
        used += cost
    context = "\n\n".join(
        _render_item(item) for item in selected
    )
    return EvidencePacket(tuple(selected), context, len(registry_items), skipped,
                          tuple(registry_items), used)


def _render_item(item: EvidenceItem) -> str:
    return (f"[{item.citation_id}] rank={item.rank} page={item.physical_page_start}-"
            f"{item.physical_page_end}\n{item.text}")


def select_evidence_packet(packet: EvidencePacket, generation_top_k: int = 10,
                           max_context_tokens: int = 6000) -> EvidencePacket:
    """Select a bounded generation view without discarding the registry."""
    registry = list(packet.registry.values())
    selected: list[EvidenceItem] = []
    used = 0
    skipped = 0
    for item in registry[:generation_top_k]:
        cost = _estimate_tokens(item.text)
        if used + cost > max_context_tokens:
            skipped += 1
            continue
        selected.append(item)
        used += cost
    return EvidencePacket(tuple(selected), "\n\n".join(_render_item(item) for item in selected),
                          len(registry), skipped, tuple(registry), used)

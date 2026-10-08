from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.legal import LegalChunk, LegalCorpusVersion, LegalDocument, LegalDocumentVersion
from app.services.indexing.embeddings import EmbeddingProvider
from app.services.legal.models import LegalEvidence, LegalQuery
from app.services.reranking.models import Reranker
from app.services.retrieval.bm25 import LocalBM25
from app.services.retrieval.fusion import reciprocal_rank_fusion
from app.services.retrieval.models import ChunkMetadata, DenseResult, RetrievalMode, SparseResult


class LegalRetrievalService:
    """Hybrid retrieval over legal_chunks only.

    Contract chunks are never queried by this service. Legal evidence keeps its
    corpus/document/version provenance so callers can build an auditable result.
    """

    def __init__(self, provider: EmbeddingProvider | None = None,
                 reranker: Reranker | None = None, rrf_k: int = 60) -> None:
        self.provider = provider
        self.reranker = reranker
        self.bm25 = LocalBM25()
        self.rrf_k = rrf_k

    async def _rows(self, session: AsyncSession, query: LegalQuery) -> list[tuple[LegalChunk, LegalDocumentVersion, LegalDocument, LegalCorpusVersion]]:
        result = await session.execute(select(LegalChunk, LegalDocumentVersion, LegalDocument, LegalCorpusVersion)
            .join(LegalDocumentVersion, LegalDocumentVersion.id == LegalChunk.legal_document_version_id)
            .join(LegalDocument, LegalDocument.id == LegalDocumentVersion.legal_document_id)
            .join(LegalCorpusVersion, LegalCorpusVersion.id == LegalDocument.corpus_version_id)
            .where(LegalCorpusVersion.id == query.corpus_version_id)
            .order_by(LegalChunk.id.asc()))
        return [(row[0], row[1], row[2], row[3]) for row in result.all()]

    @staticmethod
    def _metadata(row: tuple[LegalChunk, LegalDocumentVersion, LegalDocument, LegalCorpusVersion]) -> ChunkMetadata:
        chunk, version, document, corpus = row
        return ChunkMetadata(
            chunk_id=chunk.id, document_id=document.id, document_version_id=version.id,
            text=chunk.text, physical_page_start=chunk.physical_page_start,
            physical_page_end=chunk.physical_page_end, printed_page_label=None,
            section_identifier=chunk.section_identifier, section_title=document.title,
            clause_number=chunk.article_identifier, clause_title=chunk.section_identifier,
            chunk_type="LEGAL", extraction_method="legal-corpus",
            source_block_provenance=chunk.source_provenance, tenant_id=None, corpus="legal",
            source_type=document.source_type, source_citation=document.citation,
            corpus_version_id=corpus.id, legal_document_version_id=version.id,
            subsection_identifier=chunk.subsection_identifier,
            paragraph_identifier=chunk.paragraph_identifier)

    @staticmethod
    def _evidence(result: ChunkMetadata, rank: int, evidence_id: str) -> LegalEvidence:
        if result.corpus_version_id is None:
            raise ValueError("legal result is missing corpus version provenance")
        return LegalEvidence(evidence_id=evidence_id, legal_chunk_id=result.chunk_id,
            legal_document_version_id=result.legal_document_version_id or result.document_version_id,
            corpus_version_id=result.corpus_version_id, text=result.text,
            source_type=result.source_type or "unknown", source_citation=result.source_citation,
            title=result.section_title or "", section_identifier=result.section_identifier,
            subsection_identifier=result.subsection_identifier, article_identifier=result.clause_number,
            paragraph_identifier=result.paragraph_identifier, physical_page_start=result.physical_page_start,
            physical_page_end=result.physical_page_end, source_provenance=result.source_block_provenance)

    async def search(self, session: AsyncSession, query: LegalQuery, *, mode: RetrievalMode = RetrievalMode.HYBRID) -> list[LegalEvidence]:
        if query.tenant_id is None:
            raise PermissionError("tenant scope is required for legal retrieval")
        rows = await self._rows(session, query)
        metadata = [self._metadata(row) for row in rows]
        candidate_k = max(query.top_k, query.top_k * 5)
        dense: list[DenseResult] = []
        sparse: list[SparseResult] = []
        if mode in (RetrievalMode.DENSE, RetrievalMode.HYBRID):
            if self.provider is None:
                raise RuntimeError("Legal dense retrieval requires an embedding provider")
            vector = self.provider.embed_query(query.text)
            distance = LegalChunk.embedding.cosine_distance(vector).label("distance")
            dense_rows = await session.execute(select(LegalChunk, distance)
                .join(LegalDocumentVersion, LegalDocumentVersion.id == LegalChunk.legal_document_version_id)
                .join(LegalDocument, LegalDocument.id == LegalDocumentVersion.legal_document_id)
                .where(LegalDocument.corpus_version_id == query.corpus_version_id)
                .order_by(distance.asc(), LegalChunk.id.asc()).limit(candidate_k))
            by_id = {item.chunk_id: item for item in metadata}
            dense = [DenseResult(metadata=by_id[row[0].id], score=1.0 - float(row[1]), rank=rank)
                     for rank, row in enumerate(dense_rows.all(), 1) if row[0].id in by_id]
        if mode in (RetrievalMode.SPARSE, RetrievalMode.HYBRID):
            sparse = self.bm25.search(query.text, metadata, candidate_k)
        if mode == RetrievalMode.DENSE:
            merged = [DenseResult(metadata=x.metadata, score=x.score, rank=x.rank) for x in dense[:query.top_k]]
            ordered = [x.metadata for x in merged]
        elif mode == RetrievalMode.SPARSE:
            ordered = [x.metadata for x in sparse[:query.top_k]]
        else:
            ordered = [x.metadata for x in reciprocal_rank_fusion(dense, sparse, candidate_k, self.rrf_k)]
        if self.reranker and ordered:
            from app.services.retrieval.models import HybridResult
            reranked = self.reranker.rerank(query.text, [HybridResult(metadata=x, final_rank=i) for i, x in enumerate(ordered, 1)])
            ordered = [item.result.metadata for item in reranked[:query.top_k]]
        return [self._evidence(item, rank, f"L{rank}") for rank, item in enumerate(ordered[:query.top_k], 1)]

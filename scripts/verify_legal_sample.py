"""Verify retrieval, reranking, evidence, and citation gates for the legal sample."""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.models.legal import LegalCorpusVersion
from app.services.indexing.embeddings import LocalE5EmbeddingProvider
from app.services.legal.evidence import assess_evidence, verify_legal_citations
from app.services.legal.models import LegalAnalysis, LegalCitation, LegalQuery
from app.services.legal.retrieval import LegalRetrievalService
from app.services.reranking.service import LocalCrossEncoderReranker
from app.services.retrieval.models import RetrievalMode


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            corpus = await session.scalar(select(LegalCorpusVersion).where(
                LegalCorpusVersion.release_identifier == "sample-v1"))
            if corpus is None:
                raise RuntimeError("legal case-law sample corpus is missing")
            reranker = LocalCrossEncoderReranker(settings) if settings.reranker_enabled else None
            service = LegalRetrievalService(LocalE5EmbeddingProvider(settings), reranker)
            query = LegalQuery(text="Patna High Court case disposition", deterministic_text="case disposition",
                tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"), corpus_version_id=corpus.id, top_k=1)
            evidence = await service.search(session, query, mode=RetrievalMode.HYBRID)
            gate = assess_evidence(evidence)
            if not gate.sufficient:
                raise RuntimeError(gate.reason)
            analysis = LegalAnalysis(answer="The source record states a disposed Patna High Court case.",
                citations=[LegalCitation(evidence_id=evidence[0].evidence_id, quote=evidence[0].text)],
                evidence_gate=gate)
            verified = verify_legal_citations(analysis, evidence)
            print({"evidence": len(evidence), "first_evidence_id": evidence[0].evidence_id,
                "reranking_enabled": reranker is not None, "citations": len(verified.citations),
                "source_identifier": evidence[0].source_provenance[0].get("source_identifier")})
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

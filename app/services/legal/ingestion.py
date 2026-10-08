from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.legal import LegalChunk, LegalCorpusVersion, LegalDocument, LegalDocumentVersion
from app.services.datasets.legal import (
    LegalDatasetRecord,
    content_checksum,
    map_sample_record,
    stable_uuid,
)
from app.services.indexing.embeddings import EmbeddingProvider

NAMESPACE = uuid.UUID("a2c89d68-c2d2-4b6f-bf7a-3b2fa97f4f71")


async def import_legal_records(session: AsyncSession, provider: EmbeddingProvider,
                               rows: Sequence[dict[str, Any]], source_uri: str,
                               mapper: Callable[[dict[str, Any]], LegalDatasetRecord] = map_sample_record) -> int:
    """Import source-backed legal records into versioned legal retrieval tables."""
    if not rows:
        raise ValueError("legal corpus contains no records")
    records = [mapper(row) for row in rows]
    if any(not record.text.strip() for record in records):
        raise ValueError("legal corpus contains an empty record")
    chunk_ids = [stable_uuid(NAMESPACE, f"chunk:{record.source_identifier}") for record in records]
    existing_ids = set((await session.execute(select(LegalChunk.id).where(
        LegalChunk.id.in_(chunk_ids)))).scalars().all())
    pending = [(record, chunk_id) for record, chunk_id in zip(records, chunk_ids, strict=True)
               if chunk_id not in existing_ids]
    if not pending:
        return 0
    vectors = provider.embed_documents([record.text for record, _ in pending])
    imported = 0
    for (record, chunk_id), vector in zip(pending, vectors, strict=True):
        corpus = await session.scalar(select(LegalCorpusVersion).where(
            LegalCorpusVersion.corpus_name == record.corpus_name,
            LegalCorpusVersion.release_identifier == record.release_identifier))
        if corpus is None:
            corpus = LegalCorpusVersion(
                id=stable_uuid(NAMESPACE, f"corpus:{record.corpus_name}:{record.release_identifier}"),
                corpus_name=record.corpus_name, release_identifier=record.release_identifier,
                source_uri=source_uri, source_checksum=content_checksum(record.text),
                legal_metadata={"source": "admin-upload"})
            session.add(corpus)
            await session.flush()
        document_id = stable_uuid(NAMESPACE, f"document:{record.source_identifier}")
        version_id = stable_uuid(NAMESPACE, f"version:{record.source_identifier}")
        document = await session.get(LegalDocument, document_id)
        if document is None:
            document = LegalDocument(id=document_id, corpus_version_id=corpus.id, title=record.title,
                source_type=record.source_type, citation=record.citation, publisher=record.publisher,
                source_uri=record.source_uri, jurisdiction=record.jurisdiction,
                legal_metadata=record.metadata)
            session.add(document)
            await session.flush()
        version = LegalDocumentVersion(id=version_id, legal_document_id=document.id,
            version_label=record.release_identifier, source_identifier=record.source_identifier,
            effective_date=record.effective_date, content_checksum=content_checksum(record.text))
        session.add(version)
        await session.flush()
        session.add(LegalChunk(id=chunk_id, legal_document_version_id=version.id, chunk_index=0,
            text=record.text, content_hash=content_checksum(record.text),
            source_provenance=[record.metadata], embedding=vector,
            embedding_provider=provider.provider, embedding_model=provider.model,
            embedding_dimension=provider.dimension))
        imported += 1
    await session.commit()
    return imported

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import Callable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.services.indexing.chunking import ChunkDraft, HierarchicalChunker
from app.services.indexing.embeddings import (
    EmbeddingProvider,
    LocalE5EmbeddingProvider,
    embedding_config_hash,
)
from app.services.ingestion.processing_models import ProcessedDocument
from app.services.ingestion.storage import ObjectStorage
from app.services.ingestion.validation import processed_storage_key

logger = logging.getLogger(__name__)


class IndexingService:
    def __init__(self, settings: Settings, provider_factory: Callable[[Settings], EmbeddingProvider] | None = None) -> None:
        self.settings = settings
        self.chunker = HierarchicalChunker(settings)
        self._provider: EmbeddingProvider | None = None
        self._provider_factory = provider_factory or LocalE5EmbeddingProvider

    def provider(self) -> EmbeddingProvider:
        if self._provider is None:
            self._provider = self._provider_factory(self.settings)
        return self._provider

    async def index_processed(
        self, session: AsyncSession, tenant_id: uuid.UUID, processed: ProcessedDocument
    ) -> int:
        started = time.monotonic()
        version_result = await session.execute(
            select(DocumentVersion, Document).join(Document, Document.id == DocumentVersion.document_id).where(
                DocumentVersion.id == processed.version_id
            )
        )
        row = version_result.one_or_none()
        if row is None or row[0].document_id != processed.document_id:
            raise ValueError("Processed document does not belong to the requested document version")
        version, document = row
        if document.tenant_id is not None and document.tenant_id != tenant_id:
            raise PermissionError("Tenant scope does not match the document")

        drafts = self.chunker.chunk(processed)
        if not drafts:
            version.status = DocumentStatus.FAILED
            version.failure_reason = "Document indexing produced no chunks"
            await session.commit()
            raise ValueError("Document indexing produced no chunks")
        try:
            provider = self.provider()
            if provider.dimension != self.settings.embedding_dimension:
                raise ValueError("Embedding provider dimension does not match configured dimension")
        except Exception:
            await session.rollback()
            failed_version = await session.get(DocumentVersion, processed.version_id)
            if failed_version is not None:
                failed_version.status = DocumentStatus.FAILED
                failed_version.failure_reason = "Embedding provider configuration failed"
                await session.commit()
            raise
        config_hash = embedding_config_hash(provider)
        existing = (await session.execute(select(Chunk).where(Chunk.document_version_id == version.id))).scalars().all()
        if existing and {chunk.logical_identity for chunk in existing} == {draft.identity for draft in drafts}:
            version.status = DocumentStatus.READY
            await session.commit()
            logger.info("document_indexing_skipped_existing document_version_id=%s tenant_id=%s chunks=%s",
                        version.id, tenant_id, len(existing))
            return len(existing)

        try:
            vectors = await self._embed_with_reuse(session, drafts, provider, config_hash)
            await session.execute(delete(Chunk).where(Chunk.document_version_id == version.id))
            ids: dict[str, uuid.UUID] = {}
            for draft, vector in zip(drafts, vectors, strict=True):
                if len(vector) != self.settings.embedding_dimension:
                    raise ValueError("Embedding vector dimension mismatch")
                # Stable IDs make deterministic tie-breaking reproducible
                # across fixture rebuilds and production reindexing.
                ids[draft.identity] = uuid.uuid5(
                    uuid.NAMESPACE_URL, f"icia:chunk:{version.id}:{draft.identity}"
                )
            for draft, vector in zip(drafts, vectors, strict=True):
                session.add(Chunk(
                    id=ids[draft.identity], tenant_id=tenant_id, document_id=version.document_id,
                    document_version_id=version.id,
                    parent_chunk_id=ids.get(draft.parent_identity) if draft.parent_identity else None,
                    chunk_index=draft.chunk_index, section_identifier=draft.section_identifier,
                    section_title=draft.section_title, clause_number=draft.clause_number,
                    clause_title=draft.clause_title, chunk_type=draft.chunk_type, text=draft.text,
                    token_count=draft.token_count, content_hash=hashlib.sha256(draft.text.encode("utf-8")).hexdigest(),
                    logical_identity=draft.identity, physical_page_start=draft.physical_page_start,
                    physical_page_end=draft.physical_page_end, printed_page_label=draft.printed_page_label,
                    extraction_method=draft.extraction_method,
                    source_block_provenance=draft.source_block_provenance, embedding=vector,
                    embedding_provider=provider.provider, embedding_model=provider.model,
                    embedding_dimension=provider.dimension, embedding_config_hash=config_hash,
                ))
            await session.commit()
        except Exception:
            await session.rollback()
            failed_version = await session.get(DocumentVersion, processed.version_id)
            if failed_version is not None:
                failed_version.status = DocumentStatus.FAILED
                failed_version.failure_reason = "Document indexing failed"
                await session.commit()
            logger.exception("document_indexing_failed document_version_id=%s tenant_id=%s", processed.version_id, tenant_id)
            raise
        version.status = DocumentStatus.READY
        version.failure_reason = None
        await session.commit()
        logger.info("document_indexing_completed document_version_id=%s tenant_id=%s chunks=%s embedding_model=%s dimension=%s duration=%.3f",
                    processed.version_id, tenant_id, len(drafts), provider.model, provider.dimension, time.monotonic() - started)
        return len(drafts)

    async def _embed_with_reuse(self, session: AsyncSession, drafts: list[ChunkDraft], provider: EmbeddingProvider,
                                config_hash: str) -> list[list[float]]:
        cached: dict[tuple[str, str], list[float]] = {}
        for chunk in (await session.execute(select(Chunk).where(Chunk.embedding_config_hash == config_hash))).scalars():
            cached[(chunk.content_hash, config_hash)] = list(chunk.embedding)
        missing: list[ChunkDraft] = []
        vectors: dict[str, list[float]] = {}
        for draft in drafts:
            content_hash = hashlib.sha256(draft.text.encode("utf-8")).hexdigest()
            vector = cached.get((content_hash, config_hash))
            if vector is None:
                missing.append(draft)
            else:
                vectors[draft.identity] = vector
        for start in range(0, len(missing), self.settings.embedding_batch_size):
            batch = missing[start:start + self.settings.embedding_batch_size]
            for draft, vector in zip(batch, provider.embed_documents([item.text for item in batch]), strict=True):
                vectors[draft.identity] = list(vector)
        return [vectors[draft.identity] for draft in drafts]


async def index_stored_version(session: AsyncSession, storage: ObjectStorage, tenant_id: uuid.UUID,
                               document_id: uuid.UUID, version_id: uuid.UUID, settings: Settings) -> int:
    data = await storage.download(processed_storage_key(document_id, version_id))
    processed = ProcessedDocument.model_validate(json.loads(data))
    return await IndexingService(settings).index_processed(session, tenant_id, processed)

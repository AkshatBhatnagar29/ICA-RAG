"""Load the small checked-in legal source sample into the Phase 10 schema."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.models.legal import LegalChunk, LegalCorpusVersion, LegalDocument, LegalDocumentVersion
from app.services.datasets.legal import content_checksum, map_sample_record, stable_uuid
from app.services.indexing.embeddings import LocalE5EmbeddingProvider

NAMESPACE = uuid.UUID("a2c89d68-c2d2-4b6f-bf7a-3b2fa97f4f71")


async def seed() -> None:
    settings = get_settings()
    rows = json.loads((ROOT / "data/samples/legal_source_sample_v1.json").read_text(encoding="utf-8"))["records"]
    provider = LocalE5EmbeddingProvider(settings)
    vectors = provider.embed_documents([str(row["text"]) for row in rows])
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        for corpus_name, release in sorted({(str(row["corpus"]), str(row["release"])) for row in rows}):
            corpus = await session.scalar(select(LegalCorpusVersion).where(
                LegalCorpusVersion.corpus_name == corpus_name, LegalCorpusVersion.release_identifier == release))
            if corpus is None:
                corpus = LegalCorpusVersion(id=stable_uuid(NAMESPACE, f"corpus:{corpus_name}:{release}"),
                    corpus_name=corpus_name, release_identifier=release,
                    source_uri="derived:data/samples/legal_source_sample_v1.json",
                    legal_metadata={"sample_version": "legal-source-sample-v1"})
                session.add(corpus)
                await session.flush()
            for index, row in enumerate(rows):
                if (row["corpus"], row["release"]) != (corpus_name, release):
                    continue
                record = map_sample_record(row)
                document_id = stable_uuid(NAMESPACE, f"document:{record.source_identifier}")
                version_id = stable_uuid(NAMESPACE, f"version:{record.source_identifier}")
                document = await session.get(LegalDocument, document_id)
                if document is None:
                    session.add(LegalDocument(id=document_id, corpus_version_id=corpus.id, title=record.title,
                        source_type=record.source_type, citation=record.citation, publisher=record.publisher,
                        source_uri=record.source_uri, jurisdiction=record.jurisdiction, legal_metadata=record.metadata))
                    await session.flush()
                    session.add(LegalDocumentVersion(id=version_id, legal_document_id=document_id,
                        version_label=record.release_identifier,
                        source_identifier=record.source_identifier, effective_date=record.effective_date,
                        content_checksum=content_checksum(record.text)))
                    await session.flush()
                    session.add(LegalChunk(id=stable_uuid(NAMESPACE, f"chunk:{record.source_identifier}"),
                        legal_document_version_id=version_id, chunk_index=0, text=record.text,
                        content_hash=content_checksum(record.text), source_provenance=[record.metadata],
                        embedding=vectors[index], embedding_provider=provider.provider, embedding_model=provider.model,
                        embedding_dimension=provider.dimension))
        await session.commit()
    await engine.dispose()
    print(f"Seeded {len(rows)} source-backed legal sample records.")


if __name__ == "__main__":
    asyncio.run(seed())

"""Seed a small, clearly synthetic Phase 5 retrieval fixture."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import uuid
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.services.indexing.embeddings import LocalE5EmbeddingProvider, embedding_config_hash

FIXTURE_NAMESPACE = uuid.UUID("8cc7a9b8-1c5c-4b5a-92bb-a3ad9b1a9b52")
FIXTURE_DOCUMENT_ID = uuid.uuid5(FIXTURE_NAMESPACE, "synthetic-phase-5-contract")
FIXTURE_VERSION_ID = uuid.uuid5(FIXTURE_NAMESPACE, "synthetic-phase-5-contract-v1")
FIXTURE_TENANT_ID = uuid.uuid5(FIXTURE_NAMESPACE, "synthetic-phase-5-tenant")
ROWS = [
    ("7", "Termination", "7.1", "Notice", "Either party may terminate this Agreement by providing thirty days prior written notice."),
    ("8", "Indemnification", "8.1", "Supplier indemnity", "The Supplier shall indemnify and hold harmless the Customer from all claims, losses, and damages."),
    ("9", "Limitation of Liability", "9.1", "Liability cap", "The aggregate liability of either party shall not exceed the fees paid under this Agreement."),
    ("10", "Automatic Renewal", "10.1", "Renewal", "This Agreement shall automatically renew for successive one-year periods unless either party provides notice."),
    ("11", "Governing Law", "11.1", "Indian law", "This Agreement shall be governed by the laws of India and subject to its jurisdiction."),
    ("12", "Miscellaneous", "12.3(a)", "Notices", "Notices under Section 12.3(a) shall be delivered in writing to the address stated in this Agreement."),
]


async def seed(tenant_id: uuid.UUID) -> None:
    settings = get_settings()
    provider = LocalE5EmbeddingProvider(settings)
    vectors = provider.embed_documents([row[4] for row in ROWS])
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(delete(Document).where(Document.id == FIXTURE_DOCUMENT_ID))
        session.add(Document(id=FIXTURE_DOCUMENT_ID, tenant_id=tenant_id,
                             title="Synthetic Phase 5 Retrieval Fixture",
                             document_type="test_fixture", description="Synthetic test data only"))
        session.add(DocumentVersion(id=FIXTURE_VERSION_ID, document_id=FIXTURE_DOCUMENT_ID,
                                    version_number=1, original_filename="synthetic-fixture.txt",
                                    storage_key="test-fixtures/synthetic-fixture.txt", mime_type="text/plain",
                                    file_size=1, sha256_checksum=hashlib.sha256(b"synthetic-fixture").hexdigest(),
                                    status=DocumentStatus.READY))
        await session.flush()
        config_hash = embedding_config_hash(provider)
        for index, ((section, section_title, clause, clause_title, text), vector) in enumerate(zip(ROWS, vectors, strict=True)):
            chunk_id = uuid.uuid5(FIXTURE_NAMESPACE, f"chunk-{index}")
            session.add(Chunk(id=chunk_id, tenant_id=tenant_id, document_id=FIXTURE_DOCUMENT_ID,
                              document_version_id=FIXTURE_VERSION_ID, chunk_index=index,
                              section_identifier=section, section_title=section_title,
                              clause_number=clause, clause_title=clause_title, chunk_type="CLAUSE",
                              text=text, token_count=len(text.split()),
                              content_hash=hashlib.sha256(text.encode()).hexdigest(),
                              logical_identity=hashlib.sha256(f"fixture-{index}".encode()).hexdigest(),
                              physical_page_start=index + 1, physical_page_end=index + 1,
                              printed_page_label=str(index + 1), extraction_method="FIXTURE",
                              source_block_provenance=[{"fixture": True, "source": "synthetic"}],
                              embedding=vector, embedding_provider=provider.provider,
                              embedding_model=provider.model, embedding_dimension=provider.dimension,
                              embedding_config_hash=config_hash))
        await session.commit()
    await engine.dispose()
    print("Seeded synthetic fixture (not a real contract).")
    print(f"tenant_id={tenant_id}")
    print(f"document_id={FIXTURE_DOCUMENT_ID}")
    print(f"document_version_id={FIXTURE_VERSION_ID}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the development-only retrieval fixture.")
    parser.add_argument("--tenant-id", type=uuid.UUID, default=FIXTURE_TENANT_ID)
    arguments = parser.parse_args()
    asyncio.run(seed(arguments.tenant_id), loop_factory=asyncio.SelectorEventLoop)

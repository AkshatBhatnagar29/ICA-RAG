"""Rebuild the canonical Standard Agreement processed artifact and chunks.

This utility is intentionally pinned to the existing document version. It
never creates a document, changes its identity, or substitutes synthetic text.
The original object must already exist at the version's recorded storage key.
"""

from __future__ import annotations

import argparse
import asyncio
import selectors
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import ResourceManager
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.services.indexing.service import IndexingService
from app.services.ingestion.pipeline import DocumentProcessingPipeline
from app.services.ingestion.storage import LocalObjectStorage
from app.services.ingestion.validation import processed_storage_key

VERSION_ID = uuid.UUID("d89c42a8-0cf3-489d-89a7-e76b3b12ced1")


async def rebuild() -> None:
    settings = get_settings()
    storage = LocalObjectStorage(Path(settings.local_storage_root))
    resources = ResourceManager(settings)
    async with resources.session_factory() as session:
        version = await session.get(DocumentVersion, VERSION_ID)
        document = await session.get(Document, version.document_id) if version else None
        if version is None or document is None:
            raise RuntimeError(f"canonical document version not found: {VERSION_ID}")
        if document.tenant_id is None or version.original_filename != "Standard-agreement.pdf":
            raise RuntimeError("canonical fixture identity or tenant scope does not match")
        if not await storage.exists(version.storage_key):
            raise RuntimeError(f"original object is missing: {version.storage_key}")
        processed = await DocumentProcessingPipeline(storage, settings).process(session, VERSION_ID)
        count = await IndexingService(settings).index_processed(session, document.tenant_id, processed)
        if version.status != DocumentStatus.READY:
            raise RuntimeError(f"rebuild did not reach READY: {version.status}")
        print({"document_id": str(document.id), "tenant_id": str(document.tenant_id),
               "document_version_id": str(VERSION_ID), "pages": processed.metadata.page_count,
               "chunks": count, "processed": await storage.exists(
                   processed_storage_key(document.id, VERSION_ID))})
    await resources.close()


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    asyncio.run(rebuild(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

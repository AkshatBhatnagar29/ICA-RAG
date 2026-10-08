"""Ingest an acquired contract through the production document pipeline."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import selectors
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import ResourceManager
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.schemas.documents import DocumentUploadMetadata
from app.services.indexing.service import IndexingService
from app.services.ingestion.documents import upload_document
from app.services.ingestion.pipeline import DocumentProcessingPipeline
from app.services.ingestion.storage import LocalObjectStorage
from app.services.ingestion.validation import processed_storage_key


async def run(args: argparse.Namespace) -> dict[str, object]:
    data = args.source.read_bytes()
    settings = get_settings()
    storage = LocalObjectStorage(Path(settings.local_storage_root))
    resources = ResourceManager(settings)
    acquired_at = datetime.now(UTC)
    checksum = hashlib.sha256(data).hexdigest()
    async with resources.session_factory() as session:
        tenant_id = None
        if args.tenant_id:
            tenant_id = uuid.UUID(args.tenant_id)
        elif args.match_tenant_to:
            canonical = await session.get(DocumentVersion, uuid.UUID(args.match_tenant_to))
            document = await session.get(Document, canonical.document_id) if canonical else None
            tenant_id = document.tenant_id if document else None
        response = await upload_document(
            session, storage,
            DocumentUploadMetadata(title=args.title, document_type="contract"),
            args.source.name, "application/pdf", data, settings, tenant_id=tenant_id,
        )
        processed = await DocumentProcessingPipeline(storage, settings).process(session, response.version_id)
        document = await session.get(Document, response.document_id)
        if document is None or document.tenant_id is None:
            raise RuntimeError("ingested document did not receive a tenant scope")
        chunk_count = await IndexingService(settings).index_processed(session, document.tenant_id, processed)
        version = await session.get(DocumentVersion, response.version_id)
        chunks_ready = chunk_count > 0
        report = {
            "acquisition": {
                "source_url": args.source_url,
                "source_organization": "Ministry of External Affairs, Government of India",
                "original_filename": args.source.name,
                "acquired_at": acquired_at.isoformat(),
                "file_size": len(data),
                "mime_type": "application/pdf",
                "sha256": checksum,
            },
            "document_id": str(response.document_id),
            "tenant_id": str(document.tenant_id),
            "document_version_id": str(response.version_id),
            "status": version.status.value if version else None,
            "processed_artifact": await storage.exists(processed_storage_key(response.document_id, response.version_id)),
            "page_count": processed.metadata.page_count,
            "chunk_count": chunk_count,
            "embeddings_indexed": chunks_ready,
            "processing_version": processed.metadata.processing_version,
        }
    await resources.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--match-tenant-to")
    parser.add_argument("--tenant-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(run(args), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Inspect production chunks for one READY document version.

This is intentionally read-only. It uses the same PostgreSQL rows consumed by
retrieval so visual inspection cannot silently drift from production data.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import selectors
import sys
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import ResourceManager
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus, DocumentVersion


def _row(chunk: Chunk, previous: Chunk | None, following: Chunk | None, preview: int) -> dict[str, Any]:
    return {
        "chunk_id": str(chunk.id),
        "chunk_index": chunk.chunk_index,
        "page_start": chunk.physical_page_start,
        "page_end": chunk.physical_page_end,
        "printed_page_label": chunk.printed_page_label,
        "section": chunk.section_identifier,
        "section_title": chunk.section_title,
        "clause": chunk.clause_number,
        "clause_title": chunk.clause_title,
        "chunk_type": chunk.chunk_type.value if hasattr(chunk.chunk_type, "value") else str(chunk.chunk_type),
        "characters": len(chunk.text),
        "tokens": chunk.token_count,
        "extraction_method": chunk.extraction_method,
        "previous_chunk_id": str(previous.id) if previous else None,
        "next_chunk_id": str(following.id) if following else None,
        "source_block_provenance": chunk.source_block_provenance,
        "text": chunk.text,
        "preview": chunk.text[:preview],
    }


async def load_chunks(args: argparse.Namespace) -> tuple[str, list[dict[str, Any]]]:
    resources = ResourceManager(get_settings())
    async with resources.session_factory() as session:
        if args.document_version_id:
            version = await session.get(DocumentVersion, args.document_version_id)
            if version is None:
                raise ValueError("document version not found")
            document = await session.get(Document, version.document_id)
        else:
            result = await session.execute(
                select(DocumentVersion, Document)
                .join(Document)
                .where(
                    DocumentVersion.original_filename.ilike(f"%{Path(args.document).stem}%"),
                    DocumentVersion.status == DocumentStatus.READY,
                )
                .order_by(DocumentVersion.created_at.desc())
            )
            row = result.first()
            if row is None:
                raise ValueError("no READY document matched --document")
            version, document = row
        if version.status != DocumentStatus.READY:
            raise ValueError("document version must be READY")
        if document is None or document.tenant_id is None:
            raise ValueError("document has no tenant scope")
        if args.tenant_id and document.tenant_id != args.tenant_id:
            raise ValueError("tenant does not match document")
        query = select(Chunk).where(
            Chunk.document_version_id == version.id,
            Chunk.tenant_id == document.tenant_id,
        )
        if args.start is not None:
            query = query.where(Chunk.chunk_index >= args.start)
        if args.end is not None:
            query = query.where(Chunk.chunk_index <= args.end)
        chunks = list((await session.execute(query.order_by(Chunk.chunk_index))).scalars().all())
        all_chunks = list((await session.execute(
            select(Chunk).where(Chunk.document_version_id == version.id).order_by(Chunk.chunk_index)
        )).scalars().all())
    await resources.close()
    by_index = {item.chunk_index: item for item in all_chunks}
    rows = [_row(item, by_index.get(item.chunk_index - 1), by_index.get(item.chunk_index + 1), args.preview)
            for item in chunks]
    return str(version.id), rows


def print_text(version_id: str, rows: list[dict[str, Any]]) -> None:
    print(f"DOCUMENT VERSION: {version_id}\nCHUNKS: {len(rows)}")
    for item in rows:
        print("\n" + "=" * 72)
        print(f"CHUNK {item['chunk_index']}  ID: {item['chunk_id']}")
        print(f"Pages: {item['page_start']}-{item['page_end']}  Section: {item['section'] or '-'}  "
              f"Clause: {item['clause'] or '-'}")
        print(f"Characters: {item['characters']}  Tokens: {item['tokens']}  "
              f"Previous: {item['previous_chunk_id'] or '-'}  Next: {item['next_chunk_id'] or '-'}")
        print(f"\nTEXT:\n{item['text']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", default="Standard-agreement.pdf")
    parser.add_argument("--document-version-id", type=uuid.UUID)
    parser.add_argument("--tenant-id", type=uuid.UUID)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--preview", type=int, default=400)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    version_id, rows = asyncio.run(load_chunks(args), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"document_version_id": version_id, "chunks": rows}, indent=2) + "\n", encoding="utf-8")
        print(args.json)
    else:
        print_text(version_id, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

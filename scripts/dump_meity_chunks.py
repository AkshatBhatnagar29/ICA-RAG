"""Print indexed MeitY chunks that contain selected evaluation terms."""

from __future__ import annotations

import asyncio
import selectors
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import ResourceManager
from app.models.chunk import Chunk


async def main() -> None:
    version_id = uuid.UUID(sys.argv[1])
    terms = sys.argv[2:] or [
        "service level", "availability", "payment", "confidential",
        "intellectual property", "security", "data", "termination",
        "indemn", "liability", "dispute", "jurisdiction", "governing law",
        "penalty", "service credit", "breach", "renew", "scope", "audit",
        "ownership",
    ]
    resources = ResourceManager(get_settings())
    try:
        async with resources.session_factory() as session:
            chunks = list((await session.execute(
                select(Chunk).where(Chunk.document_version_id == version_id)
                .order_by(Chunk.chunk_index)
            )).scalars().all())
            for chunk in chunks:
                text = chunk.text.casefold()
                if any(term in text for term in terms):
                    print(
                        f"ID={chunk.id} IDX={chunk.chunk_index} "
                        f"P={chunk.physical_page_start}-{chunk.physical_page_end} "
                        f"SEC={chunk.section_title!r} CLAUSE={chunk.clause_number!r}\n"
                        f"{chunk.text}\n---"
                    )
    finally:
        await resources.close()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))

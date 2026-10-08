import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentVersion


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_title(self, title: str, tenant_id: uuid.UUID | None) -> Document | None:
        result = await self.session.execute(
            select(Document).where(Document.title == title, Document.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def find_version_by_checksum(self, document_id: uuid.UUID, checksum: str) -> DocumentVersion | None:
        result = await self.session.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.sha256_checksum == checksum,
            )
        )
        return result.scalar_one_or_none()

    async def next_version_number(self, document_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
                DocumentVersion.document_id == document_id
            )
        )
        return int(result.scalar_one()) + 1

    async def add_document(self, document: Document) -> None:
        self.session.add(document)
        await self.session.flush()

    async def add_version(self, version: DocumentVersion) -> None:
        self.session.add(version)
        await self.session.flush()

    async def find_version(self, version_id: uuid.UUID) -> DocumentVersion | None:
        result = await self.session.execute(
            select(DocumentVersion).where(DocumentVersion.id == version_id)
        )
        return result.scalar_one_or_none()

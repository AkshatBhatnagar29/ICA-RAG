import uuid
from typing import ClassVar

import pytest

from app.core.config import Settings
from app.core.exceptions import DuplicateDocumentError
from app.models.document import Document, DocumentVersion
from app.schemas.documents import DocumentUploadMetadata
from app.services.ingestion.documents import upload_document
from app.services.ingestion.storage import ObjectStorage


class FakeSession:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeStorage(ObjectStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def download(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.objects


class FakeRepository:
    document: Document | None = None
    versions: ClassVar[list[DocumentVersion]] = []

    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def find_by_title(self, title: str, tenant_id: uuid.UUID | None) -> Document | None:
        return self.document

    async def find_version_by_checksum(self, document_id: uuid.UUID, checksum: str) -> DocumentVersion | None:
        return next((version for version in self.versions if version.sha256_checksum == checksum), None)

    async def next_version_number(self, document_id: uuid.UUID) -> int:
        return len(self.versions) + 1

    async def add_document(self, document: Document) -> None:
        document.id = uuid.uuid4()
        self.document = document

    async def add_version(self, version: DocumentVersion) -> None:
        version.id = uuid.uuid4()
        self.versions.append(version)


@pytest.mark.asyncio
async def test_upload_creates_versions_without_overwriting_previous(monkeypatch) -> None:
    FakeRepository.document = None
    FakeRepository.versions = []
    monkeypatch.setattr("app.services.ingestion.documents.DocumentRepository", FakeRepository)
    session = FakeSession()
    storage = FakeStorage()
    metadata = DocumentUploadMetadata(title="Agreement")

    first = await upload_document(session, storage, metadata, "one.pdf", "application/pdf", b"%PDF-one", Settings())
    second = await upload_document(session, storage, metadata, "two.pdf", "application/pdf", b"%PDF-two", Settings())

    assert first.version_number == 1
    assert second.version_number == 2
    assert first.version_id != second.version_id
    assert len(storage.objects) == 2


@pytest.mark.asyncio
async def test_identical_upload_returns_conflict(monkeypatch) -> None:
    FakeRepository.document = None
    FakeRepository.versions = []
    monkeypatch.setattr("app.services.ingestion.documents.DocumentRepository", FakeRepository)
    session = FakeSession()
    storage = FakeStorage()
    metadata = DocumentUploadMetadata(title="Agreement")
    await upload_document(session, storage, metadata, "one.pdf", "application/pdf", b"%PDF-same", Settings())

    with pytest.raises(DuplicateDocumentError):
        await upload_document(session, storage, metadata, "copy.pdf", "application/pdf", b"%PDF-same", Settings())

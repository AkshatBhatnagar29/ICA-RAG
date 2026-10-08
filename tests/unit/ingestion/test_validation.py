from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.exceptions import DocumentValidationError, StorageError
from app.services.ingestion.storage import LocalObjectStorage
from app.services.ingestion.validation import storage_key, validate_upload


def test_pdf_upload_is_validated_and_hashed() -> None:
    result = validate_upload("agreement.pdf", "application/pdf", b"%PDF-1.7 body", Settings())

    assert result.filename == "agreement.pdf"
    assert result.size == 13
    assert len(result.checksum) == 64


@pytest.mark.parametrize(
    ("filename", "mime_type", "data", "message"),
    [
        ("agreement.txt", "text/plain", b"text", "Only PDF"),
        ("agreement.pdf", "text/plain", b"%PDF-1.7", "Only PDF"),
        ("agreement.pdf", "application/pdf", b"not a pdf", "content"),
        ("../agreement.pdf", "application/pdf", b"%PDF-1.7", "safe filename"),
        (r"..\agreement.pdf", "application/pdf", b"%PDF-1.7", "safe filename"),
        ("agreement\x00.pdf", "application/pdf", b"%PDF-1.7", "safe filename"),
        ("agreement.pdf", "application/pdf", b"", "empty"),
    ],
)
def test_invalid_uploads_are_rejected(
    filename: str, mime_type: str, data: bytes, message: str
) -> None:
    with pytest.raises(DocumentValidationError, match=message):
        validate_upload(filename, mime_type, data, Settings())


def test_upload_size_is_configurable() -> None:
    settings = Settings(max_upload_size_mb=1)

    with pytest.raises(DocumentValidationError, match="maximum size"):
        validate_upload("agreement.pdf", "application/pdf", b"%PDF-" + b"x" * (1024 * 1024), settings)


@pytest.mark.asyncio
async def test_local_storage_round_trip_and_path_traversal_protection(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    key = storage_key("doc", "version")
    await storage.upload(key, b"content")

    assert await storage.exists(key)
    assert await storage.download(key) == b"content"
    await storage.delete(key)
    assert not await storage.exists(key)

    with pytest.raises(StorageError):
        await storage.upload("../outside", b"unsafe")

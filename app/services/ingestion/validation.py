import hashlib
from dataclasses import dataclass
from pathlib import PurePath

from app.core.config import Settings
from app.core.exceptions import DocumentValidationError

ALLOWED_TYPES = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK\x03\x04"),
}


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    mime_type: str
    size: int
    checksum: str


def validate_upload(filename: str | None, mime_type: str | None, data: bytes, settings: Settings) -> ValidatedUpload:
    if (not filename or len(filename) > 255 or PurePath(filename).name != filename or
            any(separator in filename for separator in ("/", "\\")) or
            not filename.isprintable() or filename in {".", ".."}):
        raise DocumentValidationError("A safe filename is required")
    extension = PurePath(filename).suffix.lower()
    expected = ALLOWED_TYPES.get(extension)
    if expected is None or mime_type != expected[0]:
        raise DocumentValidationError("Only PDF and DOCX files with a matching MIME type are supported")
    if not data:
        raise DocumentValidationError("Uploaded files cannot be empty")
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_size:
        raise DocumentValidationError("Uploaded file exceeds the maximum size")
    if not data.startswith(expected[1]):
        raise DocumentValidationError("Uploaded file content does not match its declared type")
    return ValidatedUpload(filename, mime_type, len(data), hashlib.sha256(data).hexdigest())


def storage_key(document_id: object, version_id: object) -> str:
    return f"documents/{document_id}/versions/{version_id}/original"


def processed_storage_key(document_id: object, version_id: object) -> str:
    return f"documents/{document_id}/versions/{version_id}/processed/document.json"

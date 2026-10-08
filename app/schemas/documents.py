import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus


class DocumentUploadMetadata(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    document_type: str = Field(default="contract", min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=5000)


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    original_filename: str
    mime_type: str
    file_size: int
    sha256_checksum: str
    status: DocumentStatus
    uploaded_at: datetime


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    status: DocumentStatus
    filename: str
    size: int
    checksum: str

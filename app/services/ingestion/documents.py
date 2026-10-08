import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import DuplicateDocumentError
from app.db.repositories.document import DocumentRepository
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.schemas.documents import DocumentUploadMetadata, DocumentUploadResponse
from app.services.ingestion.storage import ObjectStorage
from app.services.ingestion.validation import storage_key, validate_upload


async def upload_document(
    session: AsyncSession,
    storage: ObjectStorage,
    metadata: DocumentUploadMetadata,
    filename: str | None,
    mime_type: str | None,
    data: bytes,
    settings: Settings,
    tenant_id: uuid.UUID | None = None,
) -> DocumentUploadResponse:
    validated = validate_upload(filename, mime_type, data, settings)
    repository = DocumentRepository(session)
    document = await repository.find_by_title(metadata.title, tenant_id)
    if document is None:
        document = Document(title=metadata.title, tenant_id=tenant_id, document_type=metadata.document_type, description=metadata.description)
        await repository.add_document(document)
    elif metadata.description and document.description != metadata.description:
        document.description = metadata.description

    if await repository.find_version_by_checksum(document.id, validated.checksum):
        raise DuplicateDocumentError("An identical file already exists for this document")

    version = DocumentVersion(
        document_id=document.id,
        version_number=await repository.next_version_number(document.id),
        original_filename=validated.filename,
        storage_key=storage_key(document.id, uuid.uuid4()),
        mime_type=validated.mime_type,
        file_size=validated.size,
        sha256_checksum=validated.checksum,
        status=DocumentStatus.UPLOADED,
    )
    await repository.add_version(version)
    await storage.upload(version.storage_key, data)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        await storage.delete(version.storage_key)
        if "uq_document_checksum" in str(exc.orig):
            raise DuplicateDocumentError("An identical file already exists for this document") from exc
        raise
    return DocumentUploadResponse(
        document_id=document.id,
        version_id=version.id,
        version_number=version.version_number,
        status=version.status,
        filename=validated.filename,
        size=version.file_size,
        checksum=version.sha256_checksum,
    )

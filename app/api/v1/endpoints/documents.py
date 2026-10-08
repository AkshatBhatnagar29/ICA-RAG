import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile, status

from app.models.document import DocumentStatus
from app.schemas.documents import DocumentUploadMetadata, DocumentUploadResponse
from app.security.auth import REQUIRE_DOCUMENTS_WRITE, AuthContext
from app.services.indexing.service import IndexingService
from app.services.ingestion.documents import upload_document
from app.services.ingestion.pipeline import DocumentProcessingPipeline

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str, Form(...)],
    tenant_id: Annotated[uuid.UUID | None, Form()] = None,
    document_type: Annotated[str, Form()] = "contract",
    description: Annotated[str | None, Form()] = None,
    context: AuthContext = REQUIRE_DOCUMENTS_WRITE,
) -> DocumentUploadResponse:
    settings = request.app.state.settings
    data = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    metadata = DocumentUploadMetadata(title=title, document_type=document_type, description=description)
    async with request.app.state.resources.session_factory() as session:
        response = await upload_document(
            session,
            request.app.state.storage,
            metadata,
            file.filename,
            file.content_type,
            data,
            settings,
            tenant_id=context.tenant.id,
        )
        processed = await DocumentProcessingPipeline(request.app.state.storage, settings).process(session, response.version_id)
        await IndexingService(settings).index_processed(session, context.tenant.id, processed)
        response.status = DocumentStatus.READY
        return response

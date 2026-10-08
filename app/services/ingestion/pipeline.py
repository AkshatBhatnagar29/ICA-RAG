import asyncio
import json
import logging
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import DocumentProcessingError
from app.db.repositories.document import DocumentRepository
from app.models.document import DocumentStatus
from app.observability.metrics import metrics
from app.services.ingestion.parser import DOCXProcessor, PDFProcessor
from app.services.ingestion.processing_models import (
    ExtractionMethod,
    Page,
    ProcessedDocument,
    ProcessingMetadata,
)
from app.services.ingestion.storage import ObjectStorage
from app.services.ingestion.validation import processed_storage_key

logger = logging.getLogger(__name__)
PROCESSING_VERSION = "v1"


class DocumentProcessingPipeline:
    def __init__(self, storage: ObjectStorage, settings: Settings) -> None:
        self.storage = storage
        self.settings = settings

    async def process(self, session: AsyncSession, version_id: uuid.UUID) -> ProcessedDocument:
        repository = DocumentRepository(session)
        version = await repository.find_version(version_id)
        if version is None:
            raise DocumentProcessingError("Document version was not found")
        version.status = DocumentStatus.PROCESSING
        version.failure_reason = None
        await session.commit()
        await self.storage.delete(processed_storage_key(version.document_id, version.id))
        started = time.monotonic()
        logger.info("document_processing_started document_id=%s version_id=%s processing_version=%s",
                    version.document_id, version.id, PROCESSING_VERSION)
        try:
            data = await self.storage.download(version.storage_key)
            pages, warnings = await asyncio.to_thread(self._parse, data, version.mime_type)
            if not pages or not any(page.text.strip() for page in pages):
                raise DocumentProcessingError("Document extraction produced no usable text")
            methods = sorted({page.extraction_method for page in pages}, key=lambda item: item.value)
            if any(page.extraction_method == ExtractionMethod.OCR for page in pages) and \
                    any(page.extraction_method == ExtractionMethod.NATIVE_TEXT for page in pages):
                methods = [ExtractionMethod.HYBRID]
            processed = ProcessedDocument(
                document_id=version.document_id,
                version_id=version.id,
                source_filename=version.original_filename,
                mime_type=version.mime_type,
                metadata=ProcessingMetadata(
                    processing_version=PROCESSING_VERSION,
                    parser_version=PROCESSING_VERSION,
                    page_count=len(pages),
                    extraction_methods=methods,
                    ocr_used=any(page.extraction_method == ExtractionMethod.OCR for page in pages),
                    warnings=warnings,
                ),
                pages=pages,
            )
            await self.storage.upload(
                processed_storage_key(version.document_id, version.id),
                json.dumps(processed.model_dump(mode="json"), ensure_ascii=False, sort_keys=True).encode("utf-8"),
            )
            # Parsing has succeeded, but the version is not searchable until
            # chunking and embedding/index persistence complete.
            version.status = DocumentStatus.INDEXING
            await session.commit()
            logger.info("document_processing_completed document_id=%s version_id=%s page_count=%s "
                        "extraction_method=%s duration=%.3f", version.document_id, version.id,
                        len(pages), ",".join(method.value for method in methods), time.monotonic() - started)
            return processed
        except Exception as exc:
            category = "ocr_error" if exc.__class__.__name__ == "OCRProcessingError" else "ingestion_error"
            metrics.increment("ingestion_failures_total", category=category)
            await session.rollback()
            version = await repository.find_version(version_id)
            if version is not None:
                version.status = DocumentStatus.FAILED
                version.failure_reason = "Document processing failed"
                await session.commit()
            logger.exception("document_processing_failed document_id=%s version_id=%s duration=%.3f",
                             version.document_id if version else "unknown", version_id,
                             time.monotonic() - started)
            if isinstance(exc, DocumentProcessingError):
                raise
            raise DocumentProcessingError("Document processing failed") from exc
        finally:
            metrics.observe("ingestion_processing_latency_ms", (time.monotonic() - started) * 1000)

    def _parse(self, data: bytes, mime_type: str) -> tuple[list[Page], list[str]]:
        if mime_type == "application/pdf":
            return PDFProcessor(self.settings).process(data), []
        if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            native = DOCXProcessor().process(data)
            rendered = self._render_docx(data)
            if rendered is not None:
                pages = PDFProcessor(self.settings).process(rendered)
                return [page.model_copy(update={"extraction_method": ExtractionMethod.DOCX_PDF_CONVERSION})
                        for page in pages], []
            return native, ["LibreOffice was unavailable; DOCX pages have no physical page numbers"]
        raise DocumentProcessingError("Unsupported document type")

    def _render_docx(self, data: bytes) -> bytes | None:
        executable = shutil.which(self.settings.libreoffice_executable)
        if executable is None:
            return None
        with tempfile.TemporaryDirectory(prefix="icia-docx-") as directory:
            root = Path(directory)
            source = root / "source.docx"
            source.write_bytes(data)
            try:
                subprocess.run([executable, "--headless", "--convert-to", "pdf", "--outdir",
                                str(root), str(source)], capture_output=True, timeout=self.settings.processing_timeout_seconds,
                               check=True, shell=False)
            except (OSError, subprocess.SubprocessError):
                return None
            output = root / "source.pdf"
            return output.read_bytes() if output.is_file() else None

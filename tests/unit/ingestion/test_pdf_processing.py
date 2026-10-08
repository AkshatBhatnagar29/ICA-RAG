import base64
import uuid
from pathlib import Path

import fitz
import pytest

from app.core.config import Settings
from app.core.exceptions import OCRProcessingError
from app.services.indexing.chunking import HierarchicalChunker
from app.services.ingestion.parser import PDFProcessor
from app.services.ingestion.processing_models import (
    ExtractionMethod,
    ProcessedDocument,
    ProcessingMetadata,
)


def test_pdf_provenance_preserves_physical_pages() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "TERMINATION NOTICE: 30 days.")
    page = document.new_page()
    page.insert_text((72, 72), "LIABILITY CAP: INR 10,00,000.")
    data = document.tobytes()
    document.close()

    pages = PDFProcessor(Settings()).process(data)

    assert [page.physical_page_number for page in pages] == [1, 2]
    assert pages[0].extraction_method == ExtractionMethod.NATIVE_TEXT
    assert "TERMINATION NOTICE: 30 days." in pages[0].text
    assert "LIABILITY CAP: INR 10,00,000." in pages[1].text
    assert pages[1].blocks[0].block_id == "p2-b1"


def test_pdf_content_near_top_margin_is_not_dropped_as_header() -> None:
    source = Path("data/raw/contracts/icat-version1/PDFs/PDFs/Standard-agreement.pdf")
    pages = PDFProcessor(Settings()).process(source.read_bytes())
    assert "Addendum" in pages[2].text
    processed = ProcessedDocument(
        document_id=uuid.uuid4(), version_id=uuid.uuid4(), source_filename=source.name,
        mime_type="application/pdf",
        metadata=ProcessingMetadata(processing_version="v1", parser_version="v1", page_count=len(pages),
                                    extraction_methods=[ExtractionMethod.NATIVE_TEXT], ocr_used=False),
        pages=pages,
    )
    chunks = HierarchicalChunker(Settings()).chunk(processed)
    assert any("Addendum" in chunk.text for chunk in chunks if chunk.physical_page_start == 3)


def test_image_only_pdf_ocr_failure_is_not_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    document = fitz.open()
    page = document.new_page()
    page.insert_image(page.rect, stream=image)
    data = document.tobytes()
    document.close()
    processor = PDFProcessor(Settings())

    def fail(_: bytes) -> str:
        raise OCRProcessingError("OCR returned no text")

    monkeypatch.setattr(processor.ocr, "extract", fail)
    with pytest.raises(OCRProcessingError):
        processor.process(data)

import enum
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class ExtractionMethod(str, enum.Enum):
    NATIVE_TEXT = "NATIVE_TEXT"
    OCR = "OCR"
    DOCX_NATIVE = "DOCX_NATIVE"
    DOCX_PDF_CONVERSION = "DOCX_PDF_CONVERSION"
    HYBRID = "HYBRID"


class BlockType(str, enum.Enum):
    PARAGRAPH = "PARAGRAPH"
    HEADING = "HEADING"
    LIST = "LIST"
    TABLE = "TABLE"
    TABLE_ROW = "TABLE_ROW"
    TABLE_CELL = "TABLE_CELL"
    HEADER = "HEADER"
    FOOTER = "FOOTER"
    OTHER = "OTHER"


class Block(BaseModel):
    model_config = ConfigDict(frozen=True)
    block_id: str
    block_type: BlockType
    text: str
    block_position: int
    paragraph_number: int | None = None
    section: str | None = None
    bbox: tuple[float, float, float, float] | None = None


class Page(BaseModel):
    physical_page_number: int | None = None
    printed_page_label: str | None = None
    text: str
    extraction_method: ExtractionMethod
    blocks: list[Block] = Field(default_factory=list)
    ocr_confidence: float | None = None


class ProcessingMetadata(BaseModel):
    processing_version: str
    parser_version: str
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    page_count: int
    extraction_methods: list[ExtractionMethod]
    ocr_used: bool
    warnings: list[str] = Field(default_factory=list)


class ProcessedDocument(BaseModel):
    document_id: uuid.UUID
    version_id: uuid.UUID
    source_filename: str
    mime_type: str
    metadata: ProcessingMetadata
    pages: list[Page]

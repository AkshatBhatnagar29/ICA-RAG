import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import EMBEDDING_DIMENSION_DEFAULT
from app.db.base import Base


class ChunkType(str, enum.Enum):
    SECTION = "SECTION"
    CLAUSE = "CLAUSE"
    SUBCLAUSE = "SUBCLAUSE"
    PARAGRAPH = "PARAGRAPH"
    TABLE = "TABLE"
    SCHEDULE = "SCHEDULE"
    ANNEXURE = "ANNEXURE"
    OTHER = "OTHER"


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        ForeignKeyConstraint(["document_version_id", "document_id"], ["document_versions.id", "document_versions.document_id"], ondelete="CASCADE"),
        UniqueConstraint("document_version_id", "logical_identity", name="uq_chunk_version_identity"),
        Index("ix_chunks_tenant_id", "tenant_id"),
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_version_id", "document_version_id"),
        Index("ix_chunks_tenant_version", "tenant_id", "document_version_id"),
        Index("ix_chunks_version_section_clause", "document_version_id", "section_identifier", "clause_number"),
        Index("ix_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw",
              postgresql_with={"m": 16, "ef_construction": 64},
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        CheckConstraint("embedding_dimension > 0", name="ck_chunk_embedding_dimension_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    clause_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    clause_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_type: Mapped[ChunkType] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    logical_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    physical_page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    physical_page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    printed_page_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    source_block_provenance: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION_DEFAULT), nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

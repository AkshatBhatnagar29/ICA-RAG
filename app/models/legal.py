from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
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


class LegalCorpusVersion(Base):
    __tablename__ = "legal_corpus_versions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corpus_name: Mapped[str] = mapped_column(String(255), nullable=False)
    release_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    legal_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("corpus_name", "release_identifier", name="uq_legal_corpus_release"),)


class LegalDocument(Base):
    __tablename__ = "legal_documents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corpus_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_corpus_versions.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    citation: Mapped[str | None] = mapped_column(String(512), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    __table_args__ = (Index("ix_legal_documents_corpus_version", "corpus_version_id"),)


class LegalDocumentVersion(Base):
    __tablename__ = "legal_document_versions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_documents.id", ondelete="CASCADE"), nullable=False)
    version_label: Mapped[str] = mapped_column(String(128), nullable=False)
    source_identifier: Mapped[str | None] = mapped_column(String(512), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint("legal_document_id", "version_label", name="uq_legal_document_version"),)


class LegalChunk(Base):
    __tablename__ = "legal_chunks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("legal_document_versions.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subsection_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    article_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paragraph_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    physical_page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    physical_page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_provenance: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION_DEFAULT), nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        UniqueConstraint("legal_document_version_id", "chunk_index", name="uq_legal_chunk_index"),
        Index("ix_legal_chunks_document_version", "legal_document_version_id"),
        Index("ix_legal_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}),
    )

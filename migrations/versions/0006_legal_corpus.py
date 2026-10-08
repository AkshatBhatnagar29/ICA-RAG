"""Add versioned, separate legal corpus tables."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0006_legal_corpus"
down_revision: str | None = "0005_contract_comparisons"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("legal_corpus_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("corpus_name", sa.String(255), nullable=False),
        sa.Column("release_identifier", sa.String(255), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("source_checksum", sa.String(64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("corpus_name", "release_identifier", name="uq_legal_corpus_release"))
    op.create_table("legal_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("corpus_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("citation", sa.String(512), nullable=True),
        sa.Column("publisher", sa.String(255), nullable=True),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("jurisdiction", sa.String(255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["corpus_version_id"], ["legal_corpus_versions.id"], ondelete="CASCADE"))
    op.create_index("ix_legal_documents_corpus_version", "legal_documents", ["corpus_version_id"])
    op.create_table("legal_document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("legal_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_label", sa.String(128), nullable=False),
        sa.Column("source_identifier", sa.String(512), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("content_checksum", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["legal_document_id"], ["legal_documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("legal_document_id", "version_label", name="uq_legal_document_version"))
    op.create_table("legal_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("legal_document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section_identifier", sa.String(255), nullable=True),
        sa.Column("subsection_identifier", sa.String(255), nullable=True),
        sa.Column("article_identifier", sa.String(255), nullable=True),
        sa.Column("paragraph_identifier", sa.String(255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("physical_page_start", sa.Integer(), nullable=True),
        sa.Column("physical_page_end", sa.Integer(), nullable=True),
        sa.Column("source_provenance", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("embedding_provider", sa.String(128), nullable=False),
        sa.Column("embedding_model", sa.String(255), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["legal_document_version_id"], ["legal_document_versions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("legal_document_version_id", "chunk_index", name="uq_legal_chunk_index"))
    # The project uses pgvector in production; Text keeps offline migration compilation possible.
    op.create_index("ix_legal_chunks_document_version", "legal_chunks", ["legal_document_version_id"])
    op.execute("CREATE INDEX ix_legal_chunks_embedding_hnsw ON legal_chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_legal_chunks_embedding_hnsw")
    op.drop_index("ix_legal_chunks_document_version", table_name="legal_chunks")
    op.drop_table("legal_chunks")
    op.drop_table("legal_document_versions")
    op.drop_index("ix_legal_documents_corpus_version", table_name="legal_documents")
    op.drop_table("legal_documents")
    op.drop_table("legal_corpus_versions")

"""Create structure-aware chunks and vector storage.

Revision ID: 0003_chunks
Revises: 0002_documents
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0003_chunks"
down_revision: str | None = "0002_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_document_versions_id_document", "document_versions", ["id", "document_id"])
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section_identifier", sa.String(255), nullable=True),
        sa.Column("section_title", sa.Text(), nullable=True),
        sa.Column("clause_number", sa.String(128), nullable=True),
        sa.Column("clause_title", sa.Text(), nullable=True),
        sa.Column("chunk_type", sa.String(32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("logical_identity", sa.String(64), nullable=False),
        sa.Column("physical_page_start", sa.Integer(), nullable=True),
        sa.Column("physical_page_end", sa.Integer(), nullable=True),
        sa.Column("printed_page_label", sa.String(128), nullable=True),
        sa.Column("extraction_method", sa.String(64), nullable=False),
        sa.Column("source_block_provenance", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("embedding_provider", sa.String(128), nullable=False),
        sa.Column("embedding_model", sa.String(255), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("embedding_config_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_version_id", "document_id"], ["document_versions.id", "document_versions.document_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_chunk_id"], ["chunks.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("document_version_id", "logical_identity", name="uq_chunk_version_identity"),
        sa.CheckConstraint("embedding_dimension > 0", name="ck_chunk_embedding_dimension_positive"),
    )
    for name, columns in (
        ("ix_chunks_tenant_id", ["tenant_id"]),
        ("ix_chunks_document_id", ["document_id"]),
        ("ix_chunks_version_id", ["document_version_id"]),
        ("ix_chunks_tenant_version", ["tenant_id", "document_version_id"]),
        ("ix_chunks_version_section_clause", ["document_version_id", "section_identifier", "clause_number"]),
    ):
        op.create_index(name, "chunks", columns)
    op.execute("CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    for name in ("ix_chunks_version_section_clause", "ix_chunks_tenant_version", "ix_chunks_version_id", "ix_chunks_document_id", "ix_chunks_tenant_id"):
        op.drop_index(name, table_name="chunks")
    op.drop_table("chunks")
    op.drop_constraint("uq_document_versions_id_document", "document_versions", type_="unique")

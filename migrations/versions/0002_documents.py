"""Create document and document version tables.

Revision ID: 0002_documents
Revises: 0001_enable_pgvector
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_documents"
down_revision: str | None = "0001_enable_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    document_status = sa.Enum(
        "UPLOADED", "VALIDATING", "PROCESSING", "INDEXING", "READY", "FAILED",
        name="document_status", native_enum=False,
    )
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256_checksum", sa.String(length=64), nullable=False),
        sa.Column("status", document_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_version_number"),
        sa.UniqueConstraint("document_id", "sha256_checksum", name="uq_document_checksum"),
        sa.UniqueConstraint("storage_key"),
        sa.CheckConstraint("version_number > 0", name="ck_document_version_positive"),
        sa.CheckConstraint(
            "status IN ('UPLOADED', 'VALIDATING', 'PROCESSING', 'INDEXING', 'READY', 'FAILED')",
            name="ck_document_version_status",
        ),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_tenant_id", table_name="documents")
    op.drop_table("documents")

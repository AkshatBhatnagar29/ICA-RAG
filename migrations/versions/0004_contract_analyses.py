"""Add derived contract intelligence snapshots.

Revision ID: 0004_contract_analyses
Revises: 0003_chunks
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_contract_analyses"
down_revision: str | None = "0003_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contract_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_version", sa.String(32), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_version_id", "document_id"],
                                ["document_versions.id", "document_versions.document_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_version_id", "analysis_version", "configuration_hash",
                            name="uq_contract_analysis_configuration"),
    )
    op.create_index("ix_contract_analyses_tenant_id", "contract_analyses", ["tenant_id"])
    op.create_index("ix_contract_analyses_version_id", "contract_analyses", ["document_version_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_analyses_version_id", table_name="contract_analyses")
    op.drop_index("ix_contract_analyses_tenant_id", table_name="contract_analyses")
    op.drop_table("contract_analyses")

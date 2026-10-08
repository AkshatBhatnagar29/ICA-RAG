"""Add derived contract comparison snapshots.

Revision ID: 0005_contract_comparisons
Revises: 0004_contract_analyses
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_contract_comparisons"
down_revision: str | None = "0004_contract_analyses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contract_comparisons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comparison_version", sa.String(32), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "source_version_id", "target_version_id", "comparison_version", "configuration_hash", name="uq_contract_comparison_configuration"),
    )
    op.create_index("ix_contract_comparisons_tenant_id", "contract_comparisons", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_comparisons_tenant_id", table_name="contract_comparisons")
    op.drop_table("contract_comparisons")

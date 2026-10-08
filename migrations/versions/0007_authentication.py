"""add users, tenants, and tenant memberships

Revision ID: 0007_authentication
Revises: 0006_legal_corpus
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_authentication"
down_revision = "0006_legal_corpus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    role = sa.Enum("ADMIN", "REVIEWER", "VIEWER", name="auth_role", native_enum=False)
    op.create_table("tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("identifier", sa.String(128), nullable=False), sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("identifier", name="uq_tenants_identifier"))
    op.create_index("ix_tenants_identifier", "tenants", ["identifier"])
    op.create_table("users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False), sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"))
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table("tenant_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", role, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_membership"))
    op.create_index("ix_memberships_user_tenant", "tenant_memberships", ["user_id", "tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_memberships_user_tenant", table_name="tenant_memberships"); op.drop_table("tenant_memberships")
    op.drop_index("ix_users_email", table_name="users"); op.drop_table("users")
    op.drop_index("ix_tenants_identifier", table_name="tenants"); op.drop_table("tenants")

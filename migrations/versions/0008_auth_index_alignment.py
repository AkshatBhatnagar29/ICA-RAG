"""remove redundant auth indexes covered by unique constraints

Revision ID: 0008_auth_index_alignment
Revises: 0007_authentication
"""
from alembic import op

revision = "0008_auth_index_alignment"
down_revision = "0007_authentication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_tenants_identifier", table_name="tenants")
    op.drop_index("ix_users_email", table_name="users")


def downgrade() -> None:
    op.create_index("ix_tenants_identifier", "tenants", ["identifier"])
    op.create_index("ix_users_email", "users", ["email"])

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKeyConstraint, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContractAnalysis(Base):
    """The immutable source is the version; this is a replaceable derived snapshot."""

    __tablename__ = "contract_analyses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_version_id", "document_id"],
            ["document_versions.id", "document_versions.document_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("document_version_id", "analysis_version", "configuration_hash",
                         name="uq_contract_analysis_configuration"),
        Index("ix_contract_analyses_tenant_id", "tenant_id"),
        Index("ix_contract_analyses_version_id", "document_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(32), nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

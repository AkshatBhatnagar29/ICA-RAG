from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.contract_comparison import ContractComparisonRepository
from app.models.contract_analysis import ContractAnalysis
from app.models.contract_comparison import ContractComparison as ContractComparisonRow
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.services.contracts.comparison import (
    COMPARISON_VERSION,
    ComparisonError,
    ContractComparison,
    compare_contracts,
    configuration_hash,
    validate_comparison_evidence,
)
from app.services.contracts.schemas import ContractIntelligence


class ContractComparisonService:
    async def _facts(self, session: AsyncSession, tenant_id: uuid.UUID, version_id: uuid.UUID) -> ContractIntelligence:
        row = (await session.execute(select(DocumentVersion, Document).join(
            Document, Document.id == DocumentVersion.document_id).where(DocumentVersion.id == version_id))).one_or_none()
        if row is None or row[1].tenant_id != tenant_id or row[0].status != DocumentStatus.READY:
            raise PermissionError("Document version is outside the requested tenant scope")
        analysis = await session.scalar(select(ContractAnalysis).where(
            ContractAnalysis.tenant_id == tenant_id, ContractAnalysis.document_version_id == version_id
        ).order_by(ContractAnalysis.created_at.desc()))
        if analysis is None:
            raise ComparisonError("both versions must have a completed contract analysis")
        return ContractIntelligence.model_validate(analysis.payload)

    async def compare(self, session: AsyncSession, tenant_id: uuid.UUID, source_id: uuid.UUID,
                      target_id: uuid.UUID) -> ContractComparison:
        if source_id == target_id:
            raise ComparisonError("source and target versions must be different")
        source = await self._facts(session, tenant_id, source_id)
        target = await self._facts(session, tenant_id, target_id)
        result = compare_contracts(uuid.uuid4(), source, target)
        validate_comparison_evidence(result, source, target)
        repo = ContractComparisonRepository(session)
        existing = await repo.get(tenant_id, source_id, target_id, COMPARISON_VERSION, configuration_hash())
        if existing is not None:
            result.comparison_id = existing.id
        else:
            result.comparison_id = uuid.uuid4()
        payload = result.model_dump(mode="json")
        if existing is None or existing.payload != payload:
            await repo.replace(ContractComparisonRow(
                id=result.comparison_id, tenant_id=tenant_id, source_version_id=source_id,
                target_version_id=target_id, comparison_version=COMPARISON_VERSION,
                configuration_hash=configuration_hash(), status=result.status, payload=payload))
        return result

    async def get(self, session: AsyncSession, tenant_id: uuid.UUID, comparison_id: uuid.UUID) -> ContractComparison | None:
        row = await ContractComparisonRepository(session).get_by_id(tenant_id, comparison_id)
        return ContractComparison.model_validate(row.payload) if row else None

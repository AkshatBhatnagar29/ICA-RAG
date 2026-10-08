import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_analysis import ContractAnalysis


class ContractAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, tenant_id: uuid.UUID, version_id: uuid.UUID, analysis_version: str,
                  configuration_hash: str) -> ContractAnalysis | None:
        result = await self.session.execute(select(ContractAnalysis).where(
            ContractAnalysis.tenant_id == tenant_id, ContractAnalysis.document_version_id == version_id,
            ContractAnalysis.analysis_version == analysis_version,
            ContractAnalysis.configuration_hash == configuration_hash))
        return result.scalar_one_or_none()

    async def replace(self, value: ContractAnalysis) -> ContractAnalysis:
        await self.session.execute(delete(ContractAnalysis).where(
            ContractAnalysis.tenant_id == value.tenant_id,
            ContractAnalysis.document_version_id == value.document_version_id,
            ContractAnalysis.analysis_version == value.analysis_version,
            ContractAnalysis.configuration_hash == value.configuration_hash))
        self.session.add(value)
        await self.session.commit()
        return value

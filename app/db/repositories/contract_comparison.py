from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_comparison import ContractComparison


class ContractComparisonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, tenant_id: uuid.UUID, source: uuid.UUID, target: uuid.UUID,
                  version: str, configuration_hash: str) -> ContractComparison | None:
        result = await self.session.execute(select(ContractComparison).where(
            ContractComparison.tenant_id == tenant_id, ContractComparison.source_version_id == source,
            ContractComparison.target_version_id == target, ContractComparison.comparison_version == version,
            ContractComparison.configuration_hash == configuration_hash))
        return result.scalar_one_or_none()

    async def get_by_id(self, tenant_id: uuid.UUID, comparison_id: uuid.UUID) -> ContractComparison | None:
        return cast(ContractComparison | None, await self.session.scalar(select(ContractComparison).where(
            ContractComparison.tenant_id == tenant_id, ContractComparison.id == comparison_id))
        )

    async def replace(self, value: ContractComparison) -> ContractComparison:
        await self.session.execute(delete(ContractComparison).where(
            ContractComparison.tenant_id == value.tenant_id,
            ContractComparison.source_version_id == value.source_version_id,
            ContractComparison.target_version_id == value.target_version_id,
            ContractComparison.comparison_version == value.comparison_version,
            ContractComparison.configuration_hash == value.configuration_hash))
        self.session.add(value)
        await self.session.commit()
        return value

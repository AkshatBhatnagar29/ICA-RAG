import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.repositories.contract_analysis import ContractAnalysisRepository
from app.models.contract_analysis import ContractAnalysis
from app.models.document import Document, DocumentStatus, DocumentVersion

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1", reason="set RUN_DB_INTEGRATION=1 to run PostgreSQL integration tests"
)

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture
async def database():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        tenant = uuid.uuid4()
        document = Document(id=uuid.uuid4(), tenant_id=tenant, title=f"integration-{tenant}", document_type="contract")
        version = DocumentVersion(id=uuid.uuid4(), document_id=document.id, version_number=1,
            original_filename="fixture.pdf", storage_key=f"integration/{tenant}/fixture.pdf",
            mime_type="application/pdf", file_size=1, sha256_checksum=uuid.uuid4().hex,
            status=DocumentStatus.READY)
        version_two = DocumentVersion(id=uuid.uuid4(), document_id=document.id, version_number=2,
            original_filename="fixture-v2.pdf", storage_key=f"integration/{tenant}/fixture-v2.pdf",
            mime_type="application/pdf", file_size=1, sha256_checksum=uuid.uuid4().hex,
            status=DocumentStatus.READY)
        other_document = Document(id=uuid.uuid4(), tenant_id=tenant, title=f"other-{tenant}", document_type="contract")
        other_version = DocumentVersion(id=uuid.uuid4(), document_id=other_document.id, version_number=1,
            original_filename="other.pdf", storage_key=f"integration/{tenant}/other.pdf",
            mime_type="application/pdf", file_size=1, sha256_checksum=uuid.uuid4().hex,
            status=DocumentStatus.READY)
        session.add_all([document, version, version_two, other_document, other_version])
        await session.commit()
        yield factory, tenant, document, version, version_two, other_document, other_version
        await session.delete(other_document)
        await session.delete(document)
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_read_replace_and_tenant_isolation(database) -> None:
    factory, tenant, document, version, version_two, _, _ = database
    payload = {"analysis_version": "v1", "document_id": str(document.id),
               "document_version_id": str(version.id), "tenant_id": str(tenant),
               "clauses": [{"clause_id": "C1"}], "obligations": [{"obligation_id": "O1"}],
               "risks": [{"risk_id": "R1"}]}
    async with factory() as session:
        repo = ContractAnalysisRepository(session)
        value = ContractAnalysis(tenant_id=tenant, document_id=document.id, document_version_id=version.id,
            analysis_version="v1", configuration_hash="a" * 64, payload=payload)
        await repo.replace(value)
    async with factory() as session:
        repo = ContractAnalysisRepository(session)
        stored = await repo.get(tenant, version.id, "v1", "a" * 64)
        assert stored is not None
        assert stored.payload["clauses"] == [{"clause_id": "C1"}]
        assert stored.payload["obligations"] == [{"obligation_id": "O1"}]
        assert stored.payload["risks"] == [{"risk_id": "R1"}]
        replacement = ContractAnalysis(tenant_id=tenant, document_id=document.id, document_version_id=version.id,
            analysis_version="v1", configuration_hash="a" * 64, payload={**payload, "clauses": ["updated"]})
        await repo.replace(replacement)
        assert (await session.scalar(select(func.count()).select_from(ContractAnalysis).where(
            ContractAnalysis.document_version_id == version.id))) == 1
        assert await repo.get(uuid.uuid4(), version.id, "v1", "a" * 64) is None
        assert await repo.get(tenant, version_two.id, "v1", "a" * 64) is None


@pytest.mark.asyncio
async def test_foreign_key_rejects_unknown_version(database) -> None:
    factory, tenant, document, valid_version, _, other_document, _ = database
    async with factory() as session:
        session.add(ContractAnalysis(tenant_id=tenant, document_id=document.id, document_version_id=uuid.uuid4(),
                                     analysis_version="v1", configuration_hash="b" * 64, payload={}))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        session.add(ContractAnalysis(tenant_id=tenant, document_id=other_document.id, document_version_id=valid_version.id,
                                     analysis_version="v1", configuration_hash="c" * 64, payload={}))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

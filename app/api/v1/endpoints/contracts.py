import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.security.auth import (
    REQUIRE_CONTRACTS_ANALYZE,
    REQUIRE_CONTRACTS_COMPARE,
    REQUIRE_CONTRACTS_READ,
    AuthContext,
)
from app.services.contracts.comparison import CompareRequest, ContractComparison
from app.services.contracts.comparison_service import ContractComparisonService
from app.services.contracts.schemas import (
    AnalyzeRequest,
    Clause,
    ContractIntelligence,
    Obligation,
    RiskFinding,
)
from app.services.contracts.service import ContractAnalysisService

router = APIRouter(prefix="/contracts", tags=["contract intelligence"])
DB_SESSION = Depends(get_db_session)
TENANT_QUERY = Query(None)


def _analysis(request: Request) -> ContractAnalysisService:
    service = request.app.state.contract_analysis_service
    if not isinstance(service, ContractAnalysisService):
        raise TypeError("Contract analysis service is not configured")
    return service


def _comparison(request: Request) -> ContractComparisonService:
    service = request.app.state.contract_comparison_service
    if not isinstance(service, ContractComparisonService):
        raise TypeError("Contract comparison service is not configured")
    return service


@router.post("/compare", response_model=ContractComparison)
async def compare(payload: CompareRequest, request: Request, tenant_id: uuid.UUID = TENANT_QUERY,
                  session: AsyncSession = DB_SESSION,
                  context: AuthContext = REQUIRE_CONTRACTS_COMPARE) -> ContractComparison:
    try:
        return await _comparison(request).compare(session, context.tenant.id, payload.source_version_id, payload.target_version_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Document version was not found") from exc
    except Exception as exc:
        from app.services.contracts.comparison import ComparisonError
        if isinstance(exc, ComparisonError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise


@router.get("/comparisons/{comparison_id}", response_model=ContractComparison)
async def get_comparison(comparison_id: uuid.UUID, request: Request, tenant_id: uuid.UUID = TENANT_QUERY,
                         session: AsyncSession = DB_SESSION,
                         context: AuthContext = REQUIRE_CONTRACTS_READ) -> ContractComparison:
    result = await _comparison(request).get(session, context.tenant.id, comparison_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Contract comparison was not found")
    return result


@router.post("/{document_version_id}/analyze", response_model=ContractIntelligence)
async def analyze(document_version_id: uuid.UUID, payload: AnalyzeRequest, request: Request,
                  session: AsyncSession = DB_SESSION,
                  context: AuthContext = REQUIRE_CONTRACTS_ANALYZE) -> ContractIntelligence:
    try:
        return await _analysis(request).analyze(session, context.tenant.id, document_version_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Document version was not found") from exc
    except Exception as exc:
        from app.core.exceptions import DocumentProcessingError
        if isinstance(exc, DocumentProcessingError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise


async def _get(document_version_id: uuid.UUID, tenant_id: uuid.UUID, request: Request,
               session: AsyncSession, context: AuthContext) -> ContractIntelligence:
    result = await _analysis(request).get(session, context.tenant.id, document_version_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Contract analysis was not found")
    return result


@router.get("/{document_version_id}/analysis", response_model=ContractIntelligence)
async def get_analysis(document_version_id: uuid.UUID, request: Request, tenant_id: uuid.UUID = TENANT_QUERY,
                       session: AsyncSession = DB_SESSION,
                       context: AuthContext = REQUIRE_CONTRACTS_READ) -> ContractIntelligence:
    return await _get(document_version_id, tenant_id, request, session, context)


@router.get("/{document_version_id}/clauses", response_model=list[Clause])
async def get_clauses(document_version_id: uuid.UUID, request: Request, tenant_id: uuid.UUID = TENANT_QUERY,
                      session: AsyncSession = DB_SESSION,
                      context: AuthContext = REQUIRE_CONTRACTS_READ) -> list[Clause]:
    return (await _get(document_version_id, tenant_id, request, session, context)).clauses


@router.get("/{document_version_id}/obligations", response_model=list[Obligation])
async def get_obligations(document_version_id: uuid.UUID, request: Request, tenant_id: uuid.UUID = TENANT_QUERY,
                          session: AsyncSession = DB_SESSION,
                          context: AuthContext = REQUIRE_CONTRACTS_READ) -> list[Obligation]:
    return (await _get(document_version_id, tenant_id, request, session, context)).obligations


@router.get("/{document_version_id}/risks", response_model=list[RiskFinding])
async def get_risks(document_version_id: uuid.UUID, request: Request, tenant_id: uuid.UUID = TENANT_QUERY,
                    session: AsyncSession = DB_SESSION,
                    context: AuthContext = REQUIRE_CONTRACTS_READ) -> list[RiskFinding]:
    return (await _get(document_version_id, tenant_id, request, session, context)).risks

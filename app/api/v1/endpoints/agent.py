from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.security.auth import REQUIRE_AGENT_USE, AuthContext
from app.services.agents.models import AgentRequest, AgentResponse
from app.services.agents.service import AgentService

router = APIRouter(prefix="/agent", tags=["agent"])
DB_SESSION = Depends(get_db_session)


@router.post("/query", response_model=AgentResponse)
async def query(payload: AgentRequest, request: Request,
                session: AsyncSession = DB_SESSION,
                context: AuthContext = REQUIRE_AGENT_USE) -> AgentResponse:
    authorized = payload.model_copy(update={"tenant_id": context.tenant.id})
    return await AgentService(session, request.app.state.retrieval_service,
        request.app.state.contract_analysis_service, request.app.state.contract_comparison_service,
        request.app.state.legal_retrieval_service, request.app.state.agent_provider,
        request.app.state.settings.generation_top_k, request.app.state.settings.generation_max_context_tokens).run(authorized)

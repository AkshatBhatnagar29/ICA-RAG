from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    GenerationCitationError,
    GenerationConfigurationError,
    GenerationError,
    GenerationOutputValidationError,
    GenerationRateLimitError,
    GenerationTimeoutError,
)
from app.db.session import get_db_session
from app.schemas.generation import ChatCitation, ChatRequest, ChatResponse
from app.security.auth import REQUIRE_SEARCH_READ, AuthContext
from app.services.generation.citations import CitationValidationError
from app.services.generation.llm import (
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.services.generation.service import GenerationOutputError
from app.services.retrieval.models import RetrievalQuery, RetrievalScope

router = APIRouter(prefix="/chat", tags=["generation"])
DB_SESSION = Depends(get_db_session)


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request,
               session: AsyncSession = DB_SESSION,
               context: AuthContext = REQUIRE_SEARCH_READ) -> ChatResponse:
    service = request.app.state.generation_service
    retrieval_query = RetrievalQuery(query=payload.query,
        scope=RetrievalScope(tenant_id=context.tenant.id, document_id=payload.document_id,
                             document_version_id=payload.document_version_id), top_k=payload.top_k,
        mode=payload.mode, rerank=payload.rerank)
    try:
        result = await service.answer(session, retrieval_query)
    except LLMConfigurationError as exc:
        raise GenerationConfigurationError(str(exc)) from exc
    except LLMRateLimitError as exc:
        raise GenerationRateLimitError(str(exc)) from exc
    except LLMTimeoutError as exc:
        raise GenerationTimeoutError(str(exc)) from exc
    except CitationValidationError as exc:
        raise GenerationCitationError("Citation validation failed") from exc
    except GenerationOutputError as exc:
        raise GenerationOutputValidationError(str(exc)) from exc
    except LLMError as exc:
        raise GenerationError("The generation provider is unavailable") from exc
    return ChatResponse(answer=result.answer,
        citations=[ChatCitation(citation_id=item.citation_id, chunk_id=item.chunk_id,
            document_id=item.document_id, document_version_id=item.document_version_id,
            page_start=item.page_start, page_end=item.page_end,
            section_identifier=item.section_identifier, section_title=item.section_title,
            clause_identifier=item.clause_identifier) for item in result.citations],
        limitations=result.limitations,
        retrieval={"candidate_count": result.candidate_count, "evidence_count": result.evidence_count,
                   "generation_selected_count": result.evidence_count,
                   "reranker_candidate_count": result.reranker_candidate_count,
                   "reranked": result.reranked})

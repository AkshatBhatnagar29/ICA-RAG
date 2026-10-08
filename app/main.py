import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import router
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.core.logging import RequestIdFilter
from app.db.session import ResourceManager
from app.observability.middleware import RequestIdMiddleware
from app.observability.telemetry import configure_telemetry
from app.services.contracts.comparison_service import ContractComparisonService
from app.services.contracts.service import ContractAnalysisService
from app.services.generation.llm import GroqProvider
from app.services.generation.service import GenerationService
from app.services.indexing.embeddings import LocalE5EmbeddingProvider
from app.services.ingestion.storage import LocalObjectStorage
from app.services.legal.retrieval import LegalRetrievalService
from app.services.reranking.service import LocalCrossEncoderReranker
from app.services.retrieval.service import RetrievalService

settings = get_settings()
configure_telemetry(settings.log_level)
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestIdFilter())
resources = ResourceManager(settings)
storage = LocalObjectStorage(Path(settings.local_storage_root))


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    application.state.settings = settings
    application.state.resources = resources
    application.state.storage = storage
    reranker = LocalCrossEncoderReranker(settings) if settings.reranker_enabled else None
    application.state.retrieval_service = RetrievalService(
        LocalE5EmbeddingProvider(settings), rrf_k=settings.retrieval_rrf_k, reranker=reranker
    )
    application.state.generation_service = GenerationService(
        application.state.retrieval_service, GroqProvider(settings), settings
    )
    application.state.agent_provider = GroqProvider(settings)
    application.state.contract_analysis_service = ContractAnalysisService(
        storage, semantic_provider=GroqProvider(settings) if settings.groq_api_key else None
    )
    application.state.contract_comparison_service = ContractComparisonService()
    application.state.legal_retrieval_service = LegalRetrievalService(
        LocalE5EmbeddingProvider(settings), reranker=reranker, rrf_k=settings.retrieval_rrf_k
    )
    yield
    await resources.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)
app.include_router(router)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("Unhandled application error", extra={"category": _exception_category(exc)}, exc_info=exc)
    request_id = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "An internal error occurred", "request_id": request_id}},
    )


@app.exception_handler(ApplicationError)
async def handle_application_error(request: Request, exc: ApplicationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    logging.getLogger(__name__).warning("Application error", extra={"category": _error_category(exc)})
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": str(exc), "request_id": request_id}},
    )


def _error_category(exc: ApplicationError) -> str:
    code = exc.code
    if "citation" in code:
        return "citation_validation_error"
    if "document" in code or "processing" in code:
        return "ingestion_error"
    if "generation" in code:
        return "llm_provider_error"
    if "auth" in code or "token" in code:
        return "authentication_error"
    return code


def _exception_category(exc: Exception) -> str:
    if isinstance(exc, SQLAlchemyError):
        return "database_error"
    module = type(exc).__module__.lower()
    if "redis" in module:
        return "redis_error"
    return "internal_error"

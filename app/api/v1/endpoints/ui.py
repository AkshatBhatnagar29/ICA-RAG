from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError
from app.db.session import get_db_session
from app.models.auth import TenantMembership, User
from app.models.contract_analysis import ContractAnalysis
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.models.legal import LegalCorpusVersion
from app.schemas.auth import BootstrapRequest
from app.schemas.documents import DocumentUploadMetadata
from app.security.auth import AuthContext, create_access_token, get_current_context, verify_password
from app.services.agents.models import AgentRequest
from app.services.agents.service import AgentService
from app.services.contracts.schemas import ContractIntelligence
from app.services.datasets.legal import map_case_law, map_sample_record
from app.services.indexing.service import IndexingService
from app.services.ingestion.documents import upload_document
from app.services.ingestion.pipeline import DocumentProcessingPipeline
from app.services.legal.ingestion import import_legal_records
from app.services.legal.query import build_legal_query
from app.services.retrieval.models import RetrievalMode, RetrievalQuery, RetrievalScope

router = APIRouter(prefix="/ui", tags=["server-rendered UI"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[4] / "templates"))
DB_SESSION = Depends(get_db_session)


def _signup_enabled(request: Request) -> bool:
    settings = request.app.state.settings
    return settings.app_env.lower() in {"development", "test"} and bool(settings.auth_bootstrap_token)


@dataclass(frozen=True)
class DocumentView:
    document: Document
    version: DocumentVersion
    analysis: ContractIntelligence | None


async def _context(token: str | None, session: AsyncSession) -> AuthContext | None:
    if not token:
        return None
    try:
        return await get_current_context(token, None, session)
    except (HTTPException, ValueError, TypeError):
        return None


def _render(request: Request, name: str, context: dict[str, object], *, status_code: int = 200) -> HTMLResponse:
    response = templates.TemplateResponse(request=request, name=name, context=context, status_code=status_code)
    return response


def _base(context: AuthContext, *, active: str, error: str | None = None,
          notice: str | None = None) -> dict[str, object]:
    return {"auth": context, "active": active, "error": error, "notice": notice}


async def _documents(session: AsyncSession, tenant_id: uuid.UUID) -> list[DocumentView]:
    rows = (await session.execute(select(Document, DocumentVersion).join(
        DocumentVersion, DocumentVersion.document_id == Document.id).where(
            Document.tenant_id == tenant_id).order_by(Document.updated_at.desc(),
                                                       DocumentVersion.version_number.desc()))).all()
    result: list[DocumentView] = []
    seen: set[uuid.UUID] = set()
    for document, version in rows:
        if document.id in seen:
            continue
        seen.add(document.id)
        analysis = await session.scalar(select(ContractAnalysis).where(
            ContractAnalysis.tenant_id == tenant_id,
            ContractAnalysis.document_version_id == version.id).order_by(ContractAnalysis.created_at.desc()))
        facts = ContractIntelligence.model_validate(analysis.payload) if analysis else None
        result.append(DocumentView(document, version, facts))
    return result


@router.get("", response_class=HTMLResponse, response_model=None)
async def home(request: Request, access_token: Annotated[str | None, Cookie()] = None,
               session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context = await _context(access_token, session)
    if context is None:
        return _render(request, "icia.html", {"auth": None, "active": "login", "error": None,
                                                "notice": None, "signup_enabled": _signup_enabled(request)})
    return RedirectResponse("/api/v1/ui/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/login", response_model=None)
async def login(request: Request, email: Annotated[str, Form()], password: Annotated[str, Form()],
                session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    user = (await session.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
    membership = None if user is None else (await session.execute(select(TenantMembership).where(
        TenantMembership.user_id == user.id))).scalars().first()
    if user is None or membership is None or not user.is_active or not verify_password(password, user.password_hash):
        return _render(request, "icia.html", {"auth": None, "active": "login",
                                                "error": "Invalid email or password.", "notice": None,
                                                "signup_enabled": _signup_enabled(request)}, status_code=401)
    response = RedirectResponse("/api/v1/ui/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie("access_token", create_access_token(user.id, membership.tenant_id),
                        httponly=True, secure=request.url.scheme == "https", samesite="lax",
                        max_age=60 * request.app.state.settings.auth_access_token_minutes)
    return response


@router.get("/signup", response_class=HTMLResponse, response_model=None)
async def signup_page(request: Request) -> HTMLResponse:
    return _render(request, "signup.html", {"auth": None, "active": "signup", "error": None,
                                           "notice": None, "signup_enabled": _signup_enabled(request),
                                           "password_min_length": request.app.state.settings.auth_password_min_length})


@router.post("/signup", response_model=None)
async def signup(request: Request, tenant_identifier: Annotated[str, Form()],
                 tenant_name: Annotated[str, Form()], email: Annotated[str, Form()],
                 password: Annotated[str, Form()], bootstrap_token: Annotated[str, Form()],
                 session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    if not _signup_enabled(request):
        return _render(request, "signup.html", {"auth": None, "active": "signup",
            "error": "Signup is disabled. Configure a development bootstrap token first.",
            "notice": None, "signup_enabled": False,
            "password_min_length": request.app.state.settings.auth_password_min_length}, status_code=404)
    from app.api.v1.endpoints.auth import bootstrap
    try:
        await bootstrap(BootstrapRequest(tenant_identifier=tenant_identifier, tenant_name=tenant_name,
            email=email, password=password), request, bootstrap_token, session)
    except (HTTPException, ValueError, TypeError) as exc:
        return _render(request, "signup.html", {"auth": None, "active": "signup", "error": str(exc),
                                               "notice": None, "signup_enabled": True,
                                               "password_min_length": request.app.state.settings.auth_password_min_length}, status_code=422)
    return RedirectResponse("/api/v1/ui?notice=Account created; sign in", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse("/api/v1/ui", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response


async def _protected(request: Request, access_token: str | None, session: AsyncSession
                     ) -> tuple[AuthContext, RedirectResponse | None]:
    context = await _context(access_token, session)
    if context is None:
        return cast(AuthContext, None), RedirectResponse("/api/v1/ui", status_code=status.HTTP_303_SEE_OTHER)
    return context, None


@router.get("/dashboard", response_class=HTMLResponse, response_model=None)
async def dashboard(request: Request, access_token: Annotated[str | None, Cookie()] = None,
                    session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    documents = await _documents(session, context.tenant.id)
    risks = [risk for item in documents if item.analysis for risk in item.analysis.risks]
    obligations = [obligation for item in documents if item.analysis for obligation in item.analysis.obligations]
    legal_corpus_count = len((await session.execute(select(LegalCorpusVersion))).scalars().all())
    return _render(request, "icia.html", {**_base(context, active="dashboard"), "documents": documents,
                                           "risk_count": len(risks), "high_risk_count": sum(
                                               risk.severity.value in {"HIGH", "CRITICAL"} for risk in risks),
                                           "obligation_count": len(obligations),
                                           "ready_count": sum(item.version.status == DocumentStatus.READY for item in documents),
                                           "processing_count": sum(item.version.status in {
                                               DocumentStatus.UPLOADED, DocumentStatus.VALIDATING,
                                               DocumentStatus.PROCESSING, DocumentStatus.INDEXING
                                           } for item in documents),
                                           "legal_corpus_count": legal_corpus_count})


@router.get("/contracts", response_class=HTMLResponse, response_model=None)
async def contracts(request: Request, access_token: Annotated[str | None, Cookie()] = None,
                    session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    return _render(request, "icia.html", {**_base(context, active="contracts"),
                                           "documents": await _documents(session, context.tenant.id)})


@router.get("/contracts/{version_id}", response_class=HTMLResponse, response_model=None)
async def contract_detail(version_id: uuid.UUID, request: Request,
                          access_token: Annotated[str | None, Cookie()] = None,
                          session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    row = (await session.execute(select(Document, DocumentVersion).join(
        DocumentVersion, DocumentVersion.document_id == Document.id).where(
            Document.tenant_id == context.tenant.id, DocumentVersion.id == version_id))).one_or_none()
    if row is None:
        return _render(request, "icia.html", {**_base(context, active="contracts", error="Contract not found."),
                                               "documents": []}, status_code=404)
    analysis = await session.scalar(select(ContractAnalysis).where(
        ContractAnalysis.tenant_id == context.tenant.id,
        ContractAnalysis.document_version_id == version_id).order_by(ContractAnalysis.created_at.desc()))
    facts = ContractIntelligence.model_validate(analysis.payload) if analysis and row[0].document_type == "contract" else None
    return _render(request, "icia.html", {**_base(context, active="detail"), "document": row[0],
                                           "version": row[1], "analysis": facts})


@router.post("/upload", response_model=None)
async def upload(request: Request, file: UploadFile, title: Annotated[str, Form()],
                 document_type: Annotated[str, Form()] = "contract",
                 access_token: Annotated[str | None, Cookie()] = None,
                 session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    settings = request.app.state.settings
    data = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    # The SSR form predates the document-type field. Preserve its contract
    # default, but avoid silently treating an explicitly named CV/resume as a
    # contract until the form is updated by clients.
    normalized_name = f"{title} {file.filename or ''}".casefold()
    if document_type == "contract" and any(term in normalized_name for term in ("resume", "curriculum vitae", " cv")):
        document_type = "resume"
    try:
        response = await upload_document(session, request.app.state.storage,
            DocumentUploadMetadata(title=title, document_type=document_type, description=None), file.filename,
            file.content_type, data, settings, tenant_id=context.tenant.id)
        processed = await DocumentProcessingPipeline(request.app.state.storage, settings).process(session, response.version_id)
        await IndexingService(settings).index_processed(session, context.tenant.id, processed)
        return RedirectResponse(f"/api/v1/ui/contracts/{response.version_id}?notice=Contract uploaded and indexed",
                                status_code=status.HTTP_303_SEE_OTHER)
    except ApplicationError as exc:
        return _render(request, "icia.html", {**_base(context, active="upload", error=str(exc)),
                                               "documents": await _documents(session, context.tenant.id)}, status_code=422)


@router.post("/contracts/{version_id}/analyze", response_model=None)
async def analyze(version_id: uuid.UUID, request: Request,
                  access_token: Annotated[str | None, Cookie()] = None,
                  session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    try:
        document = await session.scalar(select(Document).join(
            DocumentVersion, DocumentVersion.document_id == Document.id).where(
                Document.tenant_id == context.tenant.id, DocumentVersion.id == version_id))
        if document is None:
            raise PermissionError("Document version is outside the requested tenant scope")
        if document.document_type != "contract":
            raise ValueError("Contract analysis is available only for documents classified as contract")
        await request.app.state.contract_analysis_service.analyze(session, context.tenant.id, version_id)
        return RedirectResponse(f"/api/v1/ui/contracts/{version_id}?notice=Analysis completed",
                                status_code=status.HTTP_303_SEE_OTHER)
    except (PermissionError, ApplicationError, ValueError) as exc:
        return _render(request, "icia.html", {**_base(context, active="contracts", error=str(exc)),
                                               "analysis": None}, status_code=422)


@router.get("/search", response_class=HTMLResponse, response_model=None)
async def search(request: Request, q: str = "", version_id: uuid.UUID | None = None,
                 access_token: Annotated[str | None, Cookie()] = None,
                 session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    if not q and version_id is None:
        return RedirectResponse("/api/v1/ui/ask", status_code=status.HTTP_303_SEE_OTHER)
    results = []
    error = None
    if q and version_id:
        try:
            response = await request.app.state.retrieval_service.search(session, RetrievalQuery(
                query=q, scope=RetrievalScope(tenant_id=context.tenant.id, document_version_id=version_id),
                top_k=10, mode=RetrievalMode.HYBRID))
            results = response.results
        except (PermissionError, RuntimeError, ValueError) as exc:
            error = str(exc)
    return _render(request, "icia.html", {**_base(context, active="search", error=error),
                                           "documents": await _documents(session, context.tenant.id),
                                           "results": results, "query": q, "selected_version": version_id})


@router.get("/ask", response_class=HTMLResponse, response_model=None)
async def ask_page(request: Request, access_token: Annotated[str | None, Cookie()] = None,
                   version_id: uuid.UUID | None = None,
                   session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    documents = [item for item in await _documents(session, context.tenant.id)
                 if item.document.document_type == "contract"]
    return _render(request, "icia.html", {**_base(context, active="ask"),
        "documents": documents, "query": "", "selected_version": version_id,
        "corpora": list((await session.execute(select(LegalCorpusVersion).order_by(
            LegalCorpusVersion.created_at.desc()))).scalars().all())})


@router.post("/ask", response_model=None)
async def ask(request: Request, q: Annotated[str, Form()], version_id: Annotated[uuid.UUID, Form()],
              corpus_id: Annotated[uuid.UUID | None, Form()] = None,
              access_token: Annotated[str | None, Cookie()] = None,
              session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    try:
        selected_document = await session.scalar(select(Document).join(
            DocumentVersion, DocumentVersion.document_id == Document.id).where(
                Document.tenant_id == context.tenant.id, DocumentVersion.id == version_id))
        if selected_document is None:
            raise PermissionError("Document version is outside the requested tenant scope")
        if selected_document.document_type != "contract":
            raise ValueError("Ask ICIA requires a document classified as contract; this file is not a contract")
        if corpus_id is None and any(term in q.casefold() for term in
                                     ("indian law", "legal context", "statute", "case law", "legal provision")):
            corpus_id = await session.scalar(select(LegalCorpusVersion.id).order_by(
                LegalCorpusVersion.created_at.desc()))
            if corpus_id is None:
                raise ValueError("No legal corpus is available for this question")
        result = await AgentService(session, request.app.state.retrieval_service,
            request.app.state.contract_analysis_service, request.app.state.contract_comparison_service,
            request.app.state.legal_retrieval_service, request.app.state.agent_provider,
            request.app.state.settings.generation_top_k, request.app.state.settings.generation_max_context_tokens).run(
            AgentRequest(query=q, document_version_id=version_id, corpus_version_id=corpus_id,
                         tenant_id=context.tenant.id))
        documents = [item for item in await _documents(session, context.tenant.id)
                     if item.document.document_type == "contract"]
        return _render(request, "icia.html", {**_base(context, active="ask"),
            "documents": documents, "query": q,
            "corpora": list((await session.execute(select(LegalCorpusVersion).order_by(
                LegalCorpusVersion.created_at.desc()))).scalars().all()),
            "corpus_id": corpus_id, "selected_version": version_id, "agent_result": result})
    except (PermissionError, RuntimeError, ValueError) as exc:
        documents = [item for item in await _documents(session, context.tenant.id)
                     if item.document.document_type == "contract"]
        return _render(request, "icia.html", {**_base(context, active="ask", error=str(exc)),
            "documents": documents, "query": q,
            "corpora": list((await session.execute(select(LegalCorpusVersion).order_by(
                LegalCorpusVersion.created_at.desc()))).scalars().all()), "corpus_id": corpus_id}, status_code=422)


@router.get("/compare", response_class=HTMLResponse, response_model=None)
async def compare_page(request: Request, source_id: uuid.UUID | None = None,
                       target_id: uuid.UUID | None = None,
                       access_token: Annotated[str | None, Cookie()] = None,
                       session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    comparison = None
    error = None
    if source_id and target_id:
        try:
            comparison = await request.app.state.contract_comparison_service.compare(
                session, context.tenant.id, source_id, target_id)
        except (PermissionError, ValueError) as exc:
            error = str(exc)
    return _render(request, "icia.html", {**_base(context, active="compare", error=error),
        "documents": await _documents(session, context.tenant.id), "comparison": comparison,
        "source_id": source_id, "target_id": target_id})


@router.get("/legal", response_class=HTMLResponse, response_model=None)
async def legal_page(request: Request, q: str = "", corpus_id: uuid.UUID | None = None,
                     notice: str | None = None,
                     access_token: Annotated[str | None, Cookie()] = None,
                     session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    corpora = list((await session.execute(select(LegalCorpusVersion).order_by(
        LegalCorpusVersion.created_at.desc()))).scalars().all())
    evidence = []
    error = None
    if q and corpus_id:
        try:
            evidence = await request.app.state.legal_retrieval_service.search(
                session, build_legal_query(q, context.tenant.id, corpus_id))
        except (PermissionError, RuntimeError, ValueError) as exc:
            error = str(exc)
    return _render(request, "icia.html", {**_base(context, active="legal", error=error, notice=notice),
        "corpora": corpora, "legal_results": evidence, "query": q, "corpus_id": corpus_id})


@router.post("/legal/upload", response_model=None)
async def upload_legal_corpus(request: Request, file: UploadFile,
                              access_token: Annotated[str | None, Cookie()] = None,
                              session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    if context.membership.role.value != "ADMIN":
        return _render(request, "icia.html", {**_base(context, active="legal",
            error="Administrator access is required to upload legal corpora."),
            "corpora": [], "legal_results": []}, status_code=403)
    try:
        data = await file.read(request.app.state.settings.max_upload_size_mb * 1024 * 1024 + 1)
        filename = (file.filename or "").casefold()
        mapper = None
        if filename.endswith(".parquet"):
            try:
                import pyarrow as pa  # type: ignore[import-untyped]
                from pyarrow import parquet
                rows = parquet.read_table(pa.BufferReader(data)).to_pylist()
            except ImportError as exc:
                raise RuntimeError("Parquet support is not installed") from exc
            mapper = lambda row: map_case_law(row, source_file=file.filename or "upload.parquet")
        else:
            payload = json.loads(data.decode("utf-8"))
            rows = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("upload must be a JSON object containing a records array")
        provider = request.app.state.legal_retrieval_service.provider
        if provider is None:
            raise RuntimeError("legal embedding provider is not configured")
        count = await import_legal_records(session, provider, rows, file.filename or "admin-upload",
            mapper=mapper or map_sample_record)
        return RedirectResponse(f"/api/v1/ui/legal?notice=Imported {count} legal records",
                                status_code=status.HTTP_303_SEE_OTHER)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        return _render(request, "icia.html", {**_base(context, active="legal", error=str(exc)),
            "corpora": list((await session.execute(select(LegalCorpusVersion).order_by(
                LegalCorpusVersion.created_at.desc()))).scalars().all()), "legal_results": []}, status_code=422)


@router.get("/admin", response_class=HTMLResponse, response_model=None)
async def admin_page(request: Request, access_token: Annotated[str | None, Cookie()] = None,
                     session: AsyncSession = DB_SESSION) -> HTMLResponse | RedirectResponse:
    context, redirect = await _protected(request, access_token, session)
    if redirect:
        return redirect
    if context.membership.role.value != "ADMIN":
        return _render(request, "icia.html", {**_base(context, active="admin",
            error="Administrator access is required."), "users": []}, status_code=403)
    users = (await session.execute(select(User, TenantMembership).join(
        TenantMembership, TenantMembership.user_id == User.id).where(
            TenantMembership.tenant_id == context.tenant.id).order_by(User.email))).all()
    return _render(request, "icia.html", {**_base(context, active="admin"), "users": users})

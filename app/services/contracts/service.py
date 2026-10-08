from __future__ import annotations

import hashlib
import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DocumentProcessingError
from app.db.repositories.contract_analysis import ContractAnalysisRepository
from app.models.chunk import Chunk
from app.models.contract_analysis import ContractAnalysis
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.services.contracts.evidence import validate_contract_evidence
from app.services.contracts.extraction import extract_contract_facts
from app.services.contracts.risks import evaluate_risks
from app.services.contracts.schemas import ContractIntelligence
from app.services.contracts.semantic import SemanticExtractor
from app.services.generation.context import EvidenceItem
from app.services.generation.llm import LLMProvider
from app.services.ingestion.processing_models import ProcessedDocument
from app.services.ingestion.storage import ObjectStorage
from app.services.ingestion.validation import processed_storage_key

ANALYSIS_VERSION = "v1"
logger = logging.getLogger(__name__)


class ContractAnalysisService:
    def __init__(self, storage: ObjectStorage, *, thresholds: dict[str, int] | None = None,
                 semantic_provider: LLMProvider | None = None) -> None:
        self.storage = storage
        self.semantic = SemanticExtractor(semantic_provider) if semantic_provider else None
        self.thresholds = thresholds or {"short_renewal_notice_days": 30,
                                         "long_termination_notice_days": 90,
                                         "long_confidentiality_survival_years": 5}

    @staticmethod
    def configuration_hash(thresholds: dict[str, int]) -> str:
        return hashlib.sha256(json.dumps(thresholds, sort_keys=True).encode()).hexdigest()

    async def analyze(self, session: AsyncSession, tenant_id: uuid.UUID, version_id: uuid.UUID) -> ContractIntelligence:
        row = (await session.execute(select(DocumentVersion, Document).join(
            Document, Document.id == DocumentVersion.document_id).where(DocumentVersion.id == version_id))).one_or_none()
        if row is None or row[1].tenant_id != tenant_id:
            raise PermissionError("Document version is outside the requested tenant scope")
        version, document = row
        if version.status != DocumentStatus.READY:
            raise DocumentProcessingError("A ready processed document version is required")
        try:
            processed = ProcessedDocument.model_validate(json.loads(
                (await self.storage.download(processed_storage_key(document.id, version.id))).decode("utf-8")))
        except Exception as exc:
            raise DocumentProcessingError("Processed document representation is unavailable") from exc
        if processed.document_id != document.id or processed.version_id != version.id:
            raise DocumentProcessingError("Processed representation does not match the requested version")

        rows = (await session.execute(select(Chunk).where(
            Chunk.tenant_id == tenant_id, Chunk.document_id == document.id,
            Chunk.document_version_id == version.id).order_by(Chunk.chunk_index))).scalars().all()
        items = tuple(EvidenceItem(citation_id=f"E{i + 1}", chunk_id=chunk.id, document_id=chunk.document_id,
            document_version_id=chunk.document_version_id, text=chunk.text,
            physical_page_start=chunk.physical_page_start, physical_page_end=chunk.physical_page_end,
            section_identifier=chunk.section_identifier, section_title=chunk.section_title,
            clause_identifier=chunk.clause_number, clause_title=chunk.clause_title,
            rank=i + 1, tenant_id=chunk.tenant_id) for i, chunk in enumerate(rows))
        facts = extract_contract_facts(tenant_id, document.id, version.id, list(items))
        if self.semantic and items:
            try:
                semantic = await self.semantic.extract("clause_classification", items[:10])
                if semantic.clause_type and facts.clauses:
                    facts.clauses[0].clause_type = semantic.clause_type
            except Exception:
                logger.exception("llm_extraction_failed document_version_id=%s task=clause_classification", version.id)
        validate_contract_evidence(facts, {item.citation_id: item for item in items})
        facts.risks = evaluate_risks(facts, **self.thresholds)
        validated = ContractIntelligence.model_validate(facts.model_dump(mode="python"))
        repo = ContractAnalysisRepository(session)
        existing = await repo.get(tenant_id, version.id, ANALYSIS_VERSION, self.configuration_hash(self.thresholds))
        if existing is None or existing.payload != validated.model_dump(mode="json"):
            await repo.replace(ContractAnalysis(tenant_id=tenant_id, document_id=document.id,
                document_version_id=version.id, analysis_version=ANALYSIS_VERSION,
                configuration_hash=self.configuration_hash(self.thresholds), payload=validated.model_dump(mode="json")))
        return validated

    async def get(self, session: AsyncSession, tenant_id: uuid.UUID, version_id: uuid.UUID) -> ContractIntelligence | None:
        result = await session.execute(select(ContractAnalysis).where(
            ContractAnalysis.tenant_id == tenant_id, ContractAnalysis.document_version_id == version_id).order_by(ContractAnalysis.created_at.desc()))
        row = result.scalars().first()
        return ContractIntelligence.model_validate(row.payload) if row else None

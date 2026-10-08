from __future__ import annotations

import logging
import time
import uuid

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.metrics import metrics
from app.services.agents.executor import AgentExecutor
from app.services.agents.models import (
    AgentContext,
    AgentRequest,
    AgentResponse,
    AgentState,
    AgentStatus,
    AgentTask,
    ToolResult,
    ToolStatus,
)
from app.services.agents.planner import build_plan
from app.services.agents.registry import RegisteredTool, ToolRegistry
from app.services.agents.synthesis import synthesize
from app.services.contracts.comparison_service import ContractComparisonService
from app.services.contracts.schemas import ContractIntelligence
from app.services.contracts.service import ContractAnalysisService
from app.services.generation.citations import CitationValidationError
from app.services.generation.context import EvidenceItem, EvidencePacket, build_evidence_packet
from app.services.generation.llm import LLMError, LLMProvider
from app.services.legal.evidence import assess_evidence
from app.services.legal.query import build_legal_query
from app.services.legal.retrieval import LegalRetrievalService
from app.services.retrieval.models import RetrievalMode, RetrievalQuery, RetrievalScope
from app.services.retrieval.service import RetrievalService

logger = logging.getLogger(__name__)


class SearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    document_version_id: uuid.UUID


class VersionInput(BaseModel):
    document_version_id: uuid.UUID


class ComparisonInput(BaseModel):
    source_version_id: uuid.UUID
    target_version_id: uuid.UUID


class LegalSearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    corpus_version_id: uuid.UUID


class AgentService:
    def __init__(self, session: AsyncSession, retrieval: RetrievalService,
                 analysis: ContractAnalysisService, comparison: ContractComparisonService,
                 legal: LegalRetrievalService, provider: LLMProvider | None = None,
                 generation_top_k: int = 10, max_context_tokens: int = 6000) -> None:
        self.session = session
        self.retrieval = retrieval
        self.analysis = analysis
        self.comparison = comparison
        self.legal = legal
        self.provider = provider
        self.generation_top_k = generation_top_k
        self.max_context_tokens = max_context_tokens

    def registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(RegisteredTool("contract_search", SearchInput, self._contract_search, "Search authorized contract chunks."))
        registry.register(RegisteredTool("contract_analysis", VersionInput, self._contract_analysis, "Read structured contract intelligence."))
        registry.register(RegisteredTool("contract_comparison", ComparisonInput, self._comparison, "Compare two authorized contract versions."))
        registry.register(RegisteredTool("legal_search", LegalSearchInput, self._legal_search, "Search the approved versioned legal corpus."))
        return registry

    async def _contract_search(self, value: BaseModel, context: AgentContext) -> ToolResult:
        item = SearchInput.model_validate(value)
        retrieval = await self.retrieval.search(self.session, RetrievalQuery(
            query=item.query, scope=RetrievalScope(tenant_id=context.tenant_id, document_version_id=item.document_version_id),
            top_k=10, mode=RetrievalMode.HYBRID))
        packet = build_evidence_packet(retrieval.results, generation_top_k=self.generation_top_k,
            scope=RetrievalScope(
            tenant_id=context.tenant_id, document_version_id=item.document_version_id))
        if not packet.items:
            return ToolResult(status=ToolStatus.INSUFFICIENT_EVIDENCE, message="No contract evidence was found.", evidence_domain="contract")
        return ToolResult(status=ToolStatus.SUCCESS, data=packet,
                          evidence_ids=[item.citation_id for item in packet.items], evidence_domain="contract")

    async def _contract_analysis(self, value: BaseModel, context: AgentContext) -> ToolResult:
        item = VersionInput.model_validate(value)
        result = await self.analysis.get(self.session, context.tenant_id, item.document_version_id)
        if result is None:
            return ToolResult(status=ToolStatus.NOT_FOUND, message="Contract analysis was not found.", evidence_domain="contract")
        ids = [e for clause in result.clauses for e in clause.evidence_ids]
        ids.extend(e for risk in result.risks for e in risk.evidence_ids)
        return ToolResult(status=ToolStatus.SUCCESS, data=self._packet(result, context.tenant_id),
                          evidence_ids=list(dict.fromkeys(ids)), evidence_domain="contract")

    async def _comparison(self, value: BaseModel, context: AgentContext) -> ToolResult:
        item = ComparisonInput.model_validate(value)
        result = await self.comparison.compare(self.session, context.tenant_id, item.source_version_id, item.target_version_id)
        source = await self.analysis.get(self.session, context.tenant_id, item.source_version_id)
        target = await self.analysis.get(self.session, context.tenant_id, item.target_version_id)
        packets = []
        if source is not None:
            packets.append(self._packet(source, context.tenant_id, prefix="S-"))
        if target is not None:
            packets.append(self._packet(target, context.tenant_id, prefix="T-"))
        scoped_ids = [f"S-{item}" for finding in result.findings for item in finding.source_evidence_ids]
        scoped_ids.extend(f"T-{item}" for finding in result.findings for item in finding.target_evidence_ids)
        return ToolResult(status=ToolStatus.SUCCESS, data=self._merge_packets(packets),
                          evidence_ids=list(dict.fromkeys(scoped_ids)), evidence_domain="contract")

    @staticmethod
    def _packet(facts: ContractIntelligence, tenant_id: uuid.UUID, prefix: str = "") -> EvidencePacket:
        clauses = facts.clauses
        items = tuple(EvidenceItem(citation_id=prefix + evidence_id, chunk_id=clause.chunk_id,
            document_id=facts.document_id, document_version_id=clause.document_version_id,
            text=clause.text, physical_page_start=clause.physical_page_start,
            physical_page_end=clause.physical_page_end, section_identifier=clause.section,
            section_title=None, clause_identifier=clause.clause_number, clause_title=clause.clause_title,
            rank=index, tenant_id=tenant_id)
            for index, clause in enumerate(clauses, 1)
            for evidence_id in clause.evidence_ids)
        context = "\n\n".join(f"[{item.citation_id}] {item.text}" for item in items)
        return EvidencePacket(items, context, len(items), 0)

    @staticmethod
    def _merge_packets(packets: list[EvidencePacket]) -> EvidencePacket:
        items = tuple(item for packet in packets for item in (packet.registry_items or packet.items))
        return EvidencePacket(items, "\n\n".join(f"[{item.citation_id}] {item.text}" for item in items),
                              len(items), 0, items, 0)

    async def _legal_search(self, value: BaseModel, context: AgentContext) -> ToolResult:
        item = LegalSearchInput.model_validate(value)
        evidence = await self.legal.search(self.session, build_legal_query(item.query, context.tenant_id, item.corpus_version_id))
        gate = assess_evidence(evidence)
        if not gate.sufficient:
            return ToolResult(status=ToolStatus.INSUFFICIENT_EVIDENCE, data=gate.model_dump(), message=gate.reason, evidence_domain="legal")
        return ToolResult(status=ToolStatus.SUCCESS, data=evidence, evidence_ids=[e.evidence_id for e in evidence], evidence_domain="legal")

    async def run(self, request: AgentRequest, *, request_id: uuid.UUID | None = None) -> AgentResponse:
        started = time.perf_counter()
        rid = request_id or uuid.uuid4()
        if request.tenant_id is None:
            return AgentResponse(request_id=rid, status=AgentStatus.INVALID_REQUEST,
                                 task_type=AgentTask.CONTRACT_QA,
                                 answer="An authorized tenant context is required.")
        try:
            plan = build_plan(request)
            state = AgentState(request_id=rid, context=AgentContext(tenant_id=request.tenant_id), task=plan.task, plan=plan)
        except (ValueError, TypeError) as exc:
            metrics.increment("agent_planning_failures_total")
            return AgentResponse(request_id=rid, status=AgentStatus.INVALID_REQUEST,
                                 task_type=AgentTask.CONTRACT_QA, answer=str(exc))
        state = await AgentExecutor(self.registry()).execute(state)
        answer = self._answer(state)
        warnings = list(state.errors)
        synthesis_diagnostic = None
        if state.status == AgentStatus.COMPLETED and self.provider is not None:
            contract_packets = [result.data for result in state.tool_results.values()
                                if isinstance(result.data, EvidencePacket)]
            contract_packet = self._merge_packets(contract_packets)
            legal_data = next((result.data for result in state.tool_results.values()
                               if result.evidence_domain == "legal" and isinstance(result.data, list)), [])
            try:
                synthesis = await synthesize(self.provider, request.query, contract_packet, legal_data,
                                             generation_top_k=self.generation_top_k,
                                             max_context_tokens=self.max_context_tokens)
                answer = synthesis.output.answer
                citations = [item.citation_id for item in synthesis.contract_citations]
                citations.extend(item.evidence_id for item in synthesis.legal_citations)
            except LLMError as exc:
                synthesis_diagnostic = getattr(exc, "category", "provider_error")
                metrics.increment("agent_synthesis_failures_total", category=synthesis_diagnostic)
                logger.warning("agent synthesis provider failure", extra={"category": synthesis_diagnostic})
                state.status = AgentStatus.TOOL_FAILURE
                warnings.append("final synthesis failed: " + synthesis_diagnostic)
                answer = "The request could not be completed because final evidence validation failed."
                citations = []
            except CitationValidationError as exc:
                synthesis_diagnostic = "citation_validation"
                metrics.increment("agent_synthesis_failures_total", category=synthesis_diagnostic)
                logger.warning("agent synthesis citation failure", extra={"category": synthesis_diagnostic})
                state.status = AgentStatus.TOOL_FAILURE
                warnings.append(f"final synthesis failed: citation_validation ({exc})")
                answer = "The request could not be completed because final evidence validation failed."
                citations = []
            except (ValueError, TypeError):
                synthesis_diagnostic = "structured_output"
                metrics.increment("agent_synthesis_failures_total", category=synthesis_diagnostic)
                logger.warning("agent synthesis structured-output failure", extra={"category": synthesis_diagnostic})
                state.status = AgentStatus.TOOL_FAILURE
                warnings.append("final synthesis failed: structured_output")
                answer = "The request could not be completed because final evidence validation failed."
                citations = []
        else:
            citations = state.evidence_ids
        metrics.observe("agent_duration_ms", (time.perf_counter() - started) * 1000)
        execution_steps: list[dict[str, object]] = []
        for step in plan.steps:
            step_result = state.tool_results.get(step.step_id)
            execution_steps.append({"step_id": step.step_id, "tool": step.tool_name,
                                    "status": step_result.status.value if step_result else "NOT_EXECUTED",
                                    "evidence_ids": step_result.evidence_ids if step_result else []})
        evidence: list[dict[str, object]] = []
        for result in state.tool_results.values():
            if isinstance(result.data, EvidencePacket):
                evidence.extend({"domain": "contract", "evidence_id": item.citation_id,
                                 "text": item.text, "page_start": item.physical_page_start,
                                 "page_end": item.physical_page_end, "chunk_id": str(item.chunk_id)}
                                for item in result.data.items)
            elif result.evidence_domain == "legal" and isinstance(result.data, list):
                evidence.extend({"domain": "legal", "evidence_id": item.evidence_id,
                                 "text": item.text, "title": item.title,
                                 "source_type": item.source_type,
                                 "source_citation": item.source_citation,
                                 "section": item.section_identifier,
                                 "page_start": item.physical_page_start,
                                 "page_end": item.physical_page_end}
                                for item in result.data)
        return AgentResponse(request_id=rid, status=state.status, task_type=state.task, answer=answer,
            contract_evidence=state.contract_evidence, legal_evidence=state.legal_evidence,
            citations=citations, warnings=warnings,
            execution_summary={"steps_completed": len(state.completed_steps), "tool_calls": len(state.tool_results),
                               "tools": [step.tool_name for step in plan.steps],
                               "steps": execution_steps, "evidence": evidence,
                               "synthesis_diagnostic": synthesis_diagnostic})

    @staticmethod
    def _answer(state: AgentState) -> str:
        if state.status == "INSUFFICIENT_EVIDENCE":
            return "Sufficient authorized evidence was not found for this request."
        if state.status != "COMPLETED":
            return "The request could not be completed from the authorized application tools."
        return "The requested analysis was completed from authorized evidence. See the cited evidence IDs."

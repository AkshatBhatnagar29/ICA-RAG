import asyncio
import uuid

import pytest
from pydantic import BaseModel

from app.services.agents.executor import AgentExecutor
from app.services.agents.models import (
    AgentContext,
    AgentPlan,
    AgentRequest,
    AgentState,
    AgentStatus,
    AgentStep,
    AgentTask,
    ToolResult,
    ToolStatus,
)
from app.services.agents.planner import build_plan
from app.services.agents.registry import RegisteredTool, ToolRegistry
from app.services.agents.router import route_task
from app.services.agents.synthesis import _response_shape, synthesize
from app.services.generation.citations import CitationValidationError
from app.services.generation.context import EvidenceItem, EvidencePacket
from app.services.legal.models import LegalEvidence


def request(query: str, **kwargs: object) -> AgentRequest:
    return AgentRequest(query=query, tenant_id=uuid.uuid4(), **kwargs)


def test_router_and_planner_are_deterministic() -> None:
    value = request("Compare the termination clause and explain the relevant Indian legal context.",
                    source_version_id=uuid.uuid4(), target_version_id=uuid.uuid4(), corpus_version_id=uuid.uuid4())
    assert route_task(value) == AgentTask.COMBINED_CONTRACT_LEGAL_ANALYSIS
    plan = build_plan(value)
    assert [step.tool_name for step in plan.steps] == ["contract_comparison", "legal_search"]
    combined = request("What does this contract say about termination and Indian law?",
                       document_version_id=uuid.uuid4(), corpus_version_id=uuid.uuid4())
    assert [step.tool_name for step in build_plan(combined).steps] == ["contract_search", "legal_search"]


def test_planner_rejects_missing_resource() -> None:
    with pytest.raises(ValueError, match="document_version_id"):
        build_plan(request("What is the termination period?"))


class EmptyInput(BaseModel):
    pass


async def success(_: BaseModel, __: AgentContext) -> ToolResult:
    return ToolResult(status=ToolStatus.SUCCESS, evidence_ids=["E1"], evidence_domain="contract")


async def slow(_: BaseModel, __: AgentContext) -> ToolResult:
    await asyncio.sleep(0.05)
    return ToolResult(status=ToolStatus.SUCCESS)


class Provider:
    def __init__(self, output: str) -> None:
        self.output = output
        self.user_prompt = ""

    async def generate(self, _system: str, _user: str) -> str:
        self.user_prompt = _user
        return self.output


def evidence_packet() -> EvidencePacket:
    chunk = uuid.uuid4()
    document = uuid.uuid4()
    version = uuid.uuid4()
    item = EvidenceItem("E1", chunk, document, version, "The contract requires 30 days notice.", 1, 1,
                        None, None, "4", None, 1, tenant_id=uuid.UUID(int=1))
    return EvidencePacket((item,), "[E1] The contract requires 30 days notice.", 1, 0)


def legal_evidence() -> list[LegalEvidence]:
    return [LegalEvidence(evidence_id="L1", legal_chunk_id=uuid.uuid4(), legal_document_version_id=uuid.uuid4(),
                          corpus_version_id=uuid.uuid4(), text="A legal provision concerns notice.", source_type="statute",
                          source_citation="Act", title="Act", section_identifier=None, subsection_identifier=None,
                          article_identifier="1", paragraph_identifier=None, physical_page_start=None,
                          physical_page_end=None, source_provenance=[])]


@pytest.mark.asyncio
async def test_mixed_synthesis_validates_both_evidence_namespaces() -> None:
    provider = Provider('{"answer":"The contract states notice applies; legal context is available.","citations":[{"citation_id":"E1"},{"citation_id":"L1"}]}')
    result = await synthesize(provider, "notice", evidence_packet(), legal_evidence())
    assert [item.citation_id for item in result.contract_citations] == ["E1"]
    assert [item.evidence_id for item in result.legal_citations] == ["L1"]


@pytest.mark.asyncio
async def test_synthesis_accepts_compact_string_citations_from_provider() -> None:
    result = await synthesize(Provider(
        '{"answer":"The contract states notice applies.","citations":["E1"]}'),
        "notice", evidence_packet(), [])
    assert [item.citation_id for item in result.contract_citations] == ["E1"]


@pytest.mark.asyncio
async def test_synthesis_validates_registry_backed_e1_and_e6_ids() -> None:
    first = evidence_packet().items[0]
    second = EvidenceItem("E6", uuid.uuid4(), first.document_id, first.document_version_id,
                          "The contract states the repayment term.", 2, 2, None, None, None, None, 2,
                          tenant_id=first.tenant_id)
    packet = EvidencePacket((first, second), "[E1] ...\n[E6] ...", 2, 0)
    result = await synthesize(Provider(
        '{"answer":"The contract states both provisions.","citations":[{"citation_id":"E1"},{"citation_id":"E6"}]}'),
        "notice", packet, [])
    assert [item.citation_id for item in result.contract_citations] == ["E1", "E6"]


@pytest.mark.asyncio
async def test_synthesis_rejects_hallucinated_evidence() -> None:
    provider = Provider('{"answer":"unsupported","citations":[{"citation_id":"E999"}]}')
    with pytest.raises(CitationValidationError):
        await synthesize(provider, "notice", evidence_packet(), [])


@pytest.mark.asyncio
async def test_multi_tool_synthesis_uses_global_generation_budget_and_namespaces() -> None:
    first = evidence_packet().items[0]
    contract_items = tuple(
        first if index == 0 else EvidenceItem(
            f"E{index + 1}", uuid.uuid4(), first.document_id, first.document_version_id,
            f"Contract evidence {index}", index + 1, index + 1, None, None, None, None, index + 1,
            tenant_id=first.tenant_id)
        for index in range(20)
    )
    packet = EvidencePacket(contract_items, "", 20, 0, contract_items, 0)
    legal = [LegalEvidence(evidence_id=f"L{index + 1}", legal_chunk_id=uuid.uuid4(),
             legal_document_version_id=uuid.uuid4(), corpus_version_id=uuid.uuid4(),
             text=f"Legal evidence {index}", source_type="statute", source_citation="Act",
             title="Act", section_identifier=None, subsection_identifier=None,
             article_identifier=None, paragraph_identifier=None, physical_page_start=None,
             physical_page_end=None, source_provenance=[])
            for index in range(20)]
    provider = Provider('{"answer":"bounded","citations":[{"citation_id":"E1"}]}')
    result = await synthesize(provider, "notice", packet, legal, generation_top_k=10,
                              max_context_tokens=6000)
    assert len([marker for marker in provider.user_prompt.split() if marker.startswith(("[E", "[L"))]) <= 10
    assert "[E1]" in provider.user_prompt
    assert result.contract_citations[0].citation_id == "E1"


def test_synthesis_response_shape_diagnostics_are_content_free() -> None:
    shape = _response_shape('{"answer":"secret claim","citations":[{"citation_id":"E1"}]}')
    assert shape == {"json": True, "keys": ["answer", "citations"], "citation_shape": "dict"}
    assert "secret claim" not in str(shape)


def state(plan: AgentPlan) -> AgentState:
    return AgentState(request_id=uuid.uuid4(), context=AgentContext(tenant_id=uuid.uuid4()), task=plan.task, plan=plan)


@pytest.mark.asyncio
async def test_registry_rejects_unknown_tool_and_preserves_evidence() -> None:
    registry = ToolRegistry([RegisteredTool("safe", EmptyInput, success, "safe")])
    executor = AgentExecutor(registry)
    unknown = AgentPlan(task=AgentTask.CONTRACT_QA, steps=[AgentStep(step_id="S1", tool_name="execute_shell", reason="test")], stopping_condition="stop")
    result = await executor.execute(state(unknown))
    assert result.status == AgentStatus.FAILED
    valid = AgentPlan(task=AgentTask.CONTRACT_QA, steps=[AgentStep(step_id="S1", tool_name="safe", reason="test")], stopping_condition="stop")
    result = await executor.execute(state(valid))
    assert result.contract_evidence == ["E1"]


@pytest.mark.asyncio
async def test_executor_rejects_cycles_and_times_out() -> None:
    registry = ToolRegistry([RegisteredTool("safe", EmptyInput, success, "safe"), RegisteredTool("slow", EmptyInput, slow, "slow")])
    cycle = AgentPlan(task=AgentTask.CONTRACT_QA, steps=[
        AgentStep(step_id="S1", tool_name="safe", reason="test", depends_on=["S2"]),
        AgentStep(step_id="S2", tool_name="safe", reason="test", depends_on=["S1"])], stopping_condition="stop")
    result = await AgentExecutor(registry).execute(state(cycle))
    assert result.status == AgentStatus.FAILED
    timeout_plan = AgentPlan(task=AgentTask.CONTRACT_QA, steps=[AgentStep(step_id="S1", tool_name="slow", reason="test")], stopping_condition="stop")
    result = await AgentExecutor(registry, timeout_seconds=0.001).execute(state(timeout_plan))
    assert result.tool_results["S1"].status == ToolStatus.TIMEOUT

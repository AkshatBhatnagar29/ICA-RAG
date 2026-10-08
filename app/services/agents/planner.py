from __future__ import annotations

from app.services.agents.models import AgentPlan, AgentRequest, AgentStep, AgentTask
from app.services.agents.router import route_task


def build_plan(request: AgentRequest, *, max_steps: int = 5) -> AgentPlan:
    task = route_task(request)
    version = request.document_version_id
    steps: list[AgentStep] = []
    comparison_task = task == AgentTask.CONTRACT_COMPARISON or (
        task == AgentTask.COMBINED_CONTRACT_LEGAL_ANALYSIS and
        request.source_version_id is not None and request.target_version_id is not None
    )
    if comparison_task:
        if request.source_version_id is None or request.target_version_id is None:
            raise ValueError("source_version_id and target_version_id are required for comparison")
        steps.append(AgentStep(step_id="S1", tool_name="contract_comparison", arguments={
            "source_version_id": request.source_version_id, "target_version_id": request.target_version_id},
            reason="Compare the two authorized contract versions."))
    elif task == AgentTask.CONTRACT_RISK_REVIEW:
        if version is None:
            raise ValueError("document_version_id is required for contract review")
        steps.append(AgentStep(step_id="S1", tool_name="contract_analysis", arguments={"document_version_id": version},
                               reason="Use structured contract risk findings."))
    elif task == AgentTask.LEGAL_CONTEXT:
        if request.corpus_version_id is None:
            raise ValueError("corpus_version_id is required for legal context")
        steps.append(AgentStep(step_id="S1", tool_name="legal_search", arguments={
            "corpus_version_id": request.corpus_version_id, "query": request.query},
            reason="Search the approved, versioned legal corpus."))
    elif task != AgentTask.COMBINED_CONTRACT_LEGAL_ANALYSIS:
        if version is None:
            raise ValueError("document_version_id is required for contract questions")
        steps.append(AgentStep(step_id="S1", tool_name="contract_search", arguments={"query": request.query,
            "document_version_id": version}, reason="Retrieve authorized contract evidence."))
    if task == AgentTask.COMBINED_CONTRACT_LEGAL_ANALYSIS:
        if request.corpus_version_id is None:
            raise ValueError("corpus_version_id is required for combined legal analysis")
        if not comparison_task:
            if version is None:
                raise ValueError("document_version_id is required for combined legal analysis")
            steps.insert(0, AgentStep(step_id="S1", tool_name="contract_search",
                arguments={"query": request.query, "document_version_id": version},
                reason="Retrieve authorized contract evidence."))
            steps.append(AgentStep(step_id="S2", tool_name="legal_search", arguments={
                "corpus_version_id": request.corpus_version_id, "query": request.query},
                reason="Retrieve legal context after the contract search.", depends_on=["S1"]))
            return AgentPlan(task=task, steps=steps,
                required_evidence={"contract", "legal"},
                stopping_condition="Execute the approved steps once and stop on failure or insufficient evidence.")
        steps.append(AgentStep(step_id="S2", tool_name="legal_search", arguments={
            "corpus_version_id": request.corpus_version_id, "query": request.query},
            reason="Retrieve legal context after the contract comparison.", depends_on=["S1"]))
    if len(steps) > max_steps:
        raise ValueError("agent plan exceeds the step limit")
    required = {"legal"} if task == AgentTask.LEGAL_CONTEXT else {"contract"}
    if task == AgentTask.COMBINED_CONTRACT_LEGAL_ANALYSIS:
        required = {"contract", "legal"}
    return AgentPlan(task=task, steps=steps, required_evidence=required,
                     stopping_condition="Execute the approved steps once and stop on failure or insufficient evidence.")

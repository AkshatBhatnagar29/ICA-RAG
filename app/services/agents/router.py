from __future__ import annotations

from app.services.agents.models import AgentRequest, AgentTask


def route_task(request: AgentRequest) -> AgentTask:
    text = request.query.casefold()
    comparison = request.source_version_id is not None or request.target_version_id is not None or "compar" in text
    legal = any(term in text for term in ("indian law", "legal context", "statute", "case law", "legal provision"))
    if legal and (comparison or request.document_version_id is not None):
        return AgentTask.COMBINED_CONTRACT_LEGAL_ANALYSIS
    if comparison:
        return AgentTask.CONTRACT_COMPARISON
    if any(term in text for term in ("risk", "risks", "red flag", "exposure")):
        return AgentTask.CONTRACT_RISK_REVIEW
    if legal:
        return AgentTask.LEGAL_CONTEXT
    return AgentTask.CONTRACT_QA

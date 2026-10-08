from __future__ import annotations

from app.services.contracts.schemas import ContractIntelligence
from app.services.generation.context import EvidenceItem


class ContractEvidenceError(ValueError):
    pass


def validate_contract_evidence(facts: ContractIntelligence, registry: dict[str, EvidenceItem]) -> ContractIntelligence:
    """Reject every object that cites evidence outside the authorized packet."""
    def check(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "evidence_ids":
                    if not isinstance(child, list) or any(identifier not in registry for identifier in child):
                        raise ContractEvidenceError(f"{path}.evidence_ids contains unknown evidence")
                else:
                    check(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                check(child, f"{path}[{index}]")

    check(facts.model_dump(mode="python"), "analysis")
    for clause in facts.clauses:
        if clause.document_version_id != facts.document_version_id:
            raise ContractEvidenceError("clause document version does not match analysis")
        if not clause.evidence_ids:
            raise ContractEvidenceError("clause has no evidence")
        for identifier in clause.evidence_ids:
            item = registry[identifier]
            if item.document_version_id != facts.document_version_id or item.tenant_id is not None and item.tenant_id != facts.tenant_id:
                raise ContractEvidenceError("evidence is outside analysis scope")
            if item.chunk_id != clause.chunk_id:
                raise ContractEvidenceError("clause chunk does not match cited evidence")
    return facts

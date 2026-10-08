import uuid

import pytest

from app.services.contracts.comparison import (
    AlignmentType,
    ComparisonError,
    SemanticComparisonResult,
    align_clauses,
    compare_contracts,
    textual_diff,
    validate_comparison_evidence,
    validate_semantic_comparison,
)
from app.services.contracts.schemas import Clause, ContractIntelligence


def facts(clauses: list[Clause]) -> ContractIntelligence:
    return ContractIntelligence(analysis_version="v1", document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(), tenant_id=uuid.UUID(int=1), clauses=clauses)


def clause(number: str | None, title: str, text: str, evidence: str) -> Clause:
    return Clause(clause_id=f"C-{evidence}", document_version_id=uuid.uuid4(), chunk_id=uuid.uuid4(),
        clause_number=number, clause_title=title, text=text, evidence_ids=[evidence], confidence=.9)


def test_alignment_and_text_normalization() -> None:
    left = clause("7.1", "Termination", "Terminate with 30 days notice.", "S1")
    right = clause("8.2", "Termination", "Terminate with 90 days notice.", "T1")
    alignment = align_clauses([left], [right])[0]
    assert alignment.alignment_type == AlignmentType.TITLE
    assert textual_diff("a  contract\f clause", "a contract clause") == []


def test_added_removed_modified_unchanged_and_deterministic_summary() -> None:
    source = facts([clause("1", "Payment", "Pay within 30 days.", "S1"),
                    clause("2", "Definitions", "Definitions apply.", "S2"),
                    clause("3", "Old", "This is removed.", "S3")])
    target = facts([clause("1", "Payment", "Pay within 45 days.", "T1"),
                    clause("2", "Definitions", "Definitions apply.", "T2"),
                    clause("4", "New", "This is added.", "T4")])
    result = compare_contracts(uuid.uuid4(), source, target)
    assert result.summary.added_count == 1
    assert result.summary.removed_count == 1
    assert result.summary.modified_count == 1
    assert result.summary.unchanged_count == 1
    assert [item.alignment_id for item in result.findings] == ["A1", "A3", "A4"]


def test_evidence_and_semantic_validation_fail_closed() -> None:
    source = facts([clause("1", "Payment", "Pay within 30 days.", "S1")])
    target = facts([clause("1", "Payment", "Pay within 45 days.", "T1")])
    result = compare_contracts(uuid.uuid4(), source, target)
    validate_comparison_evidence(result, source, target)
    finding = result.findings[0]
    with pytest.raises(ComparisonError):
        validate_semantic_comparison(SemanticComparisonResult(meaning_changed=True, summary="unsupported",
            confidence=.8, source_evidence_ids=["bad"], target_evidence_ids=["T1"]), finding)
    result.findings[0].source_evidence_ids = ["bad"]
    with pytest.raises(ComparisonError):
        validate_comparison_evidence(result, source, target)

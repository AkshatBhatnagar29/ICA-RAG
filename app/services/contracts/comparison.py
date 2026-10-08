from __future__ import annotations

import difflib
import hashlib
import re
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.contracts.schemas import Clause, ContractIntelligence


class ComparisonError(ValueError):
    pass


class AlignmentType(str, Enum):
    EXACT = "EXACT"
    STRUCTURAL = "STRUCTURAL"
    TITLE = "TITLE"
    TAXONOMY = "TAXONOMY"
    SEMANTIC = "SEMANTIC"
    UNCERTAIN = "UNCERTAIN"


class ChangeType(str, Enum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    UNCHANGED = "UNCHANGED"


class ChangeCategory(str, Enum):
    PARTY_CHANGE = "PARTY_CHANGE"
    OBLIGATION_CHANGE = "OBLIGATION_CHANGE"
    DEADLINE_CHANGE = "DEADLINE_CHANGE"
    NOTICE_PERIOD_CHANGE = "NOTICE_PERIOD_CHANGE"
    PAYMENT_CHANGE = "PAYMENT_CHANGE"
    RENEWAL_CHANGE = "RENEWAL_CHANGE"
    TERMINATION_CHANGE = "TERMINATION_CHANGE"
    INDEMNIFICATION_CHANGE = "INDEMNIFICATION_CHANGE"
    LIABILITY_CHANGE = "LIABILITY_CHANGE"
    CONFIDENTIALITY_CHANGE = "CONFIDENTIALITY_CHANGE"
    IP_CHANGE = "IP_CHANGE"
    GOVERNING_LAW_CHANGE = "GOVERNING_LAW_CHANGE"
    JURISDICTION_CHANGE = "JURISDICTION_CHANGE"
    DISPUTE_RESOLUTION_CHANGE = "DISPUTE_RESOLUTION_CHANGE"
    RESTRICTIVE_COVENANT_CHANGE = "RESTRICTIVE_COVENANT_CHANGE"
    OTHER_SEMANTIC_CHANGE = "OTHER_SEMANTIC_CHANGE"


class TextSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    old_text: str = ""
    new_text: str = ""


class ClauseAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alignment_id: str
    source_clause_id: str | None = None
    target_clause_id: str | None = None
    alignment_type: AlignmentType
    alignment_confidence: float = Field(ge=0, le=1)
    source_evidence_ids: list[str] = Field(default_factory=list)
    target_evidence_ids: list[str] = Field(default_factory=list)


class ComparisonFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comparison_id: uuid.UUID
    alignment_id: str
    change_type: ChangeType
    category: ChangeCategory
    title: str
    summary: str
    old_value: str | None = None
    new_value: str | None = None
    old_text: str | None = None
    new_text: str | None = None
    changed_spans: list[TextSpan] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    source_evidence_ids: list[str] = Field(default_factory=list)
    target_evidence_ids: list[str] = Field(default_factory=list)
    potential_impact: str | None = None
    rule_id: str | None = None


class ComparisonSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    added_count: int = Field(ge=0)
    removed_count: int = Field(ge=0)
    modified_count: int = Field(ge=0)
    unchanged_count: int = Field(ge=0)
    category_counts: dict[str, int] = Field(default_factory=dict)


class ContractComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comparison_id: uuid.UUID
    tenant_id: uuid.UUID
    source_version_id: uuid.UUID
    target_version_id: uuid.UUID
    comparison_version: str
    status: str = "COMPLETED"
    summary: ComparisonSummary
    alignments: list[ClauseAlignment] = Field(default_factory=list)
    findings: list[ComparisonFinding] = Field(default_factory=list)


class SemanticComparisonResult(BaseModel):
    """Validated, optional LLM interpretation for a deterministic diff."""
    model_config = ConfigDict(extra="forbid")
    meaning_changed: bool
    summary: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    source_evidence_ids: list[str] = Field(min_length=1)
    target_evidence_ids: list[str] = Field(min_length=1)


def validate_semantic_comparison(result: SemanticComparisonResult, finding: ComparisonFinding) -> SemanticComparisonResult:
    if not set(result.source_evidence_ids).issubset(finding.source_evidence_ids):
        raise ComparisonError("semantic comparison contains unsupported source evidence")
    if not set(result.target_evidence_ids).issubset(finding.target_evidence_ids):
        raise ComparisonError("semantic comparison contains unsupported target evidence")
    if result.meaning_changed and not result.summary.strip():
        raise ComparisonError("semantic comparison must explain a meaning change")
    return result


class CompareRequest(BaseModel):
    source_version_id: uuid.UUID
    target_version_id: uuid.UUID


COMPARISON_VERSION = "v1"


def configuration_hash() -> str:
    return hashlib.sha256(COMPARISON_VERSION.encode()).hexdigest()


def normalize_text(value: str) -> str:
    # Page breaks and extraction line wraps are formatting noise; punctuation,
    # numbers, names, and negations remain untouched.
    return re.sub(r"\s+", " ", value.replace("\f", " ")).strip()


def textual_diff(old: str, new: str) -> list[TextSpan]:
    old_words, new_words = normalize_text(old).split(), normalize_text(new).split()
    matcher = difflib.SequenceMatcher(a=old_words, b=new_words, autojunk=False)
    return [TextSpan(operation=tag, old_text=" ".join(old_words[i1:i2]),
                     new_text=" ".join(new_words[j1:j2]))
            for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def _key(value: str | None) -> str:
    return normalize_text(value or "").casefold()


def _title(clause: Clause) -> str:
    return _key(clause.clause_title) or _key(clause.clause_type.value)


def align_clauses(source: list[Clause], target: list[Clause]) -> list[ClauseAlignment]:
    used: set[str] = set()
    result: list[ClauseAlignment] = []

    def add(left: Clause | None, right: Clause | None, kind: AlignmentType, confidence: float) -> None:
        result.append(ClauseAlignment(alignment_id=f"A{len(result)+1}",
            source_clause_id=left.clause_id if left else None,
            target_clause_id=right.clause_id if right else None,
            alignment_type=kind, alignment_confidence=confidence,
            source_evidence_ids=left.evidence_ids if left else [],
            target_evidence_ids=right.evidence_ids if right else []))
        if right:
            used.add(right.clause_id)

    for left in source:
        candidates = [right for right in target if right.clause_id not in used]
        match: tuple[Clause, AlignmentType, float] | None = None
        for right in candidates:
            if left.clause_number and left.clause_number == right.clause_number:
                match = (right, AlignmentType.EXACT, 1.0); break
        if match is None:
            for right in candidates:
                if left.section and left.clause_number and left.section == right.section and left.clause_number == right.clause_number:
                    match = (right, AlignmentType.STRUCTURAL, .95); break
        if match is None:
            for right in candidates:
                if _title(left) and _title(left) == _title(right):
                    match = (right, AlignmentType.TITLE, .9); break
        if match is None:
            for right in candidates:
                if left.clause_type == right.clause_type and left.clause_type.value not in {"unknown", "other"}:
                    match = (right, AlignmentType.TAXONOMY, .75); break
        # Do not force a positional match: an unmatched clause is represented
        # explicitly as UNCERTAIN and becomes a removed/added finding.
        add(left, match[0], match[1], match[2]) if match else add(left, None, AlignmentType.UNCERTAIN, 0.0)
    for right in target:
        if right.clause_id not in used:
            add(None, right, AlignmentType.UNCERTAIN, 0.0)
    return result


def _period(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\b\d+\s+(?:calendar\s+|business\s+)?days?\b", value, re.IGNORECASE)
    return match.group(0) if match else None


def _fact_value(facts: ContractIntelligence, category: ChangeCategory) -> tuple[str | None, list[str]]:
    value: Any = None
    if category == ChangeCategory.NOTICE_PERIOD_CHANGE and facts.termination:
        value = facts.termination.notice_requirement
        ids = facts.termination.evidence_ids
    elif category == ChangeCategory.RENEWAL_CHANGE and facts.renewal:
        value = f"automatic={facts.renewal.automatic}; period={facts.renewal.renewal_period}"
        ids = facts.renewal.evidence_ids
    elif category == ChangeCategory.LIABILITY_CHANGE and facts.limitation_of_liability:
        value = facts.limitation_of_liability.cap_amount or facts.limitation_of_liability.liability_cap
        ids = facts.limitation_of_liability.evidence_ids
    elif category == ChangeCategory.PAYMENT_CHANGE and facts.payment:
        value = _period(facts.payment.payment_deadline) or facts.payment.payment_deadline
        ids = facts.payment.evidence_ids
    elif category == ChangeCategory.CONFIDENTIALITY_CHANGE and facts.confidentiality:
        value = _period(facts.confidentiality.survival) or facts.confidentiality.survival
        ids = facts.confidentiality.evidence_ids
    else:
        return None, []
    return (str(value) if value is not None else None), ids


def _category(left: Clause, right: Clause) -> ChangeCategory:
    mapping = {"payment": ChangeCategory.PAYMENT_CHANGE, "renewal": ChangeCategory.RENEWAL_CHANGE,
               "termination": ChangeCategory.TERMINATION_CHANGE, "termination_for_convenience": ChangeCategory.TERMINATION_CHANGE,
               "limitation_of_liability": ChangeCategory.LIABILITY_CHANGE, "confidentiality": ChangeCategory.CONFIDENTIALITY_CHANGE,
               "intellectual_property": ChangeCategory.IP_CHANGE, "indemnification": ChangeCategory.INDEMNIFICATION_CHANGE,
               "governing_law": ChangeCategory.GOVERNING_LAW_CHANGE, "jurisdiction": ChangeCategory.JURISDICTION_CHANGE,
               "non_compete": ChangeCategory.RESTRICTIVE_COVENANT_CHANGE, "non_solicit": ChangeCategory.RESTRICTIVE_COVENANT_CHANGE}
    return mapping.get(right.clause_type.value, ChangeCategory.OTHER_SEMANTIC_CHANGE)


def compare_facts(comparison_id: uuid.UUID, source: ContractIntelligence, target: ContractIntelligence,
                  alignments: list[ClauseAlignment]) -> list[ComparisonFinding]:
    findings: list[ComparisonFinding] = []
    categories = [ChangeCategory.NOTICE_PERIOD_CHANGE, ChangeCategory.RENEWAL_CHANGE,
                  ChangeCategory.LIABILITY_CHANGE, ChangeCategory.PAYMENT_CHANGE,
                  ChangeCategory.CONFIDENTIALITY_CHANGE]
    for category in categories:
        old, old_ids = _fact_value(source, category); new, new_ids = _fact_value(target, category)
        if old != new and (old is not None or new is not None):
            alignment = next((a for a in alignments if set(a.source_evidence_ids) & set(old_ids)
                              or set(a.target_evidence_ids) & set(new_ids)), None)
            if alignment is None: continue
            label = category.value.replace("_CHANGE", "").replace("_", " ").title()
            impact = None
            if category == ChangeCategory.NOTICE_PERIOD_CHANGE:
                impact = f"Termination notice changed from {old or 'not identified'} to {new or 'not identified'}, which may change the parties' ability to exit the agreement quickly."
            elif category == ChangeCategory.LIABILITY_CHANGE:
                impact = "The contractual liability cap changed, potentially changing monetary exposure."
            change_type = ChangeType.MODIFIED
            if old is None:
                change_type = ChangeType.ADDED
            elif new is None:
                change_type = ChangeType.REMOVED
            findings.append(ComparisonFinding(comparison_id=comparison_id, alignment_id=alignment.alignment_id,
                change_type=change_type, category=category, title=f"{label} {'added' if change_type == ChangeType.ADDED else 'removed' if change_type == ChangeType.REMOVED else 'changed'}",
                summary=f"{label} changed from {old or 'not identified'} to {new or 'not identified'}.",
                old_value=old, new_value=new, confidence=.9, source_evidence_ids=old_ids,
                target_evidence_ids=new_ids, potential_impact=impact, rule_id=f"RULE-COMPARISON-{category.value}"))
    return findings


def compare_contracts(comparison_id: uuid.UUID, source: ContractIntelligence,
                      target: ContractIntelligence) -> ContractComparison:
    if source.tenant_id != target.tenant_id:
        raise ComparisonError("source and target contracts must belong to the same tenant")
    if source.document_version_id == target.document_version_id:
        raise ComparisonError("source and target versions must be different")
    alignments = align_clauses(source.clauses, target.clauses)
    by_source = {c.clause_id: c for c in source.clauses}; by_target = {c.clause_id: c for c in target.clauses}
    findings = compare_facts(comparison_id, source, target, alignments)
    for alignment in alignments:
        left, right = by_source.get(alignment.source_clause_id or ""), by_target.get(alignment.target_clause_id or "")
        if left is None or right is None:
            changed = ChangeType.ADDED if left is None else ChangeType.REMOVED
            clause = right or left; assert clause is not None
            findings.append(ComparisonFinding(comparison_id=comparison_id, alignment_id=alignment.alignment_id,
                change_type=changed, category=_category(clause, clause), title=f"Clause {changed.value.lower()}",
                summary=f"Clause {clause.clause_title or clause.clause_id} was {changed.value.lower()}.",
                old_text=left.text if left else None, new_text=right.text if right else None,
                confidence=alignment.alignment_confidence, source_evidence_ids=alignment.source_evidence_ids,
                target_evidence_ids=alignment.target_evidence_ids))
        elif normalize_text(left.text) == normalize_text(right.text):
            continue
        else:
            category = _category(left, right)
            findings.append(ComparisonFinding(comparison_id=comparison_id, alignment_id=alignment.alignment_id,
                change_type=ChangeType.MODIFIED, category=category, title=f"{category.value.replace('_', ' ').title()}",
                summary="The aligned clause contains a meaningful textual change.", old_text=left.text,
                new_text=right.text, changed_spans=textual_diff(left.text, right.text),
                confidence=alignment.alignment_confidence, source_evidence_ids=left.evidence_ids,
                target_evidence_ids=right.evidence_ids))
    alignment_order = {a.alignment_id: i for i, a in enumerate(alignments)}
    findings.sort(key=lambda f: (alignment_order[f.alignment_id], f.category.value, f.alignment_id))
    counts = {kind.value: sum(1 for a in alignments if (kind == ChangeType.ADDED and a.source_clause_id is None) or (kind == ChangeType.REMOVED and a.target_clause_id is None) or (kind == ChangeType.UNCHANGED and a.source_clause_id and a.target_clause_id and normalize_text(by_source[a.source_clause_id].text) == normalize_text(by_target[a.target_clause_id].text))) for kind in ChangeType}
    counts[ChangeType.MODIFIED.value] = len(alignments) - counts[ChangeType.ADDED.value] - counts[ChangeType.REMOVED.value] - counts[ChangeType.UNCHANGED.value]
    return ContractComparison(comparison_id=comparison_id, tenant_id=source.tenant_id,
        source_version_id=source.document_version_id, target_version_id=target.document_version_id,
        comparison_version=COMPARISON_VERSION, summary=ComparisonSummary(added_count=counts["ADDED"], removed_count=counts["REMOVED"], modified_count=counts["MODIFIED"], unchanged_count=counts["UNCHANGED"], category_counts={f.category.value: sum(x.category == f.category for x in findings) for f in findings}), alignments=alignments, findings=findings)


def validate_comparison_evidence(comparison: ContractComparison, source: ContractIntelligence,
                                 target: ContractIntelligence) -> ContractComparison:
    """Fail closed when a finding cites an ID outside its aligned clause."""
    source_ids = {item for clause in source.clauses for item in clause.evidence_ids}
    target_ids = {item for clause in target.clauses for item in clause.evidence_ids}
    for finding in comparison.findings:
        if not set(finding.source_evidence_ids).issubset(source_ids):
            raise ComparisonError("finding contains unknown source evidence")
        if not set(finding.target_evidence_ids).issubset(target_ids):
            raise ComparisonError("finding contains unknown target evidence")
        alignment = next((a for a in comparison.alignments if a.alignment_id == finding.alignment_id), None)
        if alignment is None or not set(finding.source_evidence_ids).issubset(alignment.source_evidence_ids) or not set(finding.target_evidence_ids).issubset(alignment.target_evidence_ids):
            raise ComparisonError("finding evidence does not match its clause alignment")
        if finding.change_type == ChangeType.ADDED and not finding.target_evidence_ids:
            raise ComparisonError("added finding requires target evidence")
        if finding.change_type == ChangeType.REMOVED and not finding.source_evidence_ids:
            raise ComparisonError("removed finding requires source evidence")
        if finding.change_type == ChangeType.MODIFIED and (not finding.source_evidence_ids or not finding.target_evidence_ids):
            raise ComparisonError("modified finding requires source and target evidence")
    return comparison

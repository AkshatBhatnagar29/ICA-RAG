from __future__ import annotations

from collections.abc import Sequence

from app.services.legal.models import LegalAnalysis, LegalCitation, LegalEvidence, LegalEvidenceGate


def assess_evidence(evidence: Sequence[LegalEvidence], *, minimum_count: int = 1) -> LegalEvidenceGate:
    if minimum_count < 1:
        raise ValueError("minimum_count must be positive")
    if not evidence:
        return LegalEvidenceGate(sufficient=False, reason="No legal evidence was retrieved.", evidence_count=0)
    if len(evidence) < minimum_count:
        return LegalEvidenceGate(sufficient=False, reason="Retrieved legal evidence was insufficient.", evidence_count=len(evidence))
    if any(item.corpus_version_id is None or not item.text.strip() for item in evidence):
        return LegalEvidenceGate(sufficient=False, reason="Retrieved legal evidence failed provenance validation.", evidence_count=len(evidence))
    return LegalEvidenceGate(sufficient=True, reason="Retrieved legal evidence passed the evidence gate.", evidence_count=len(evidence))


def verify_legal_citations(analysis: LegalAnalysis, evidence: Sequence[LegalEvidence]) -> LegalAnalysis:
    registry = {item.evidence_id: item for item in evidence}
    seen: set[str] = set()
    verified: list[LegalCitation] = []
    for citation in analysis.citations:
        if citation.evidence_id in seen:
            raise ValueError("duplicate legal evidence ID")
        item = registry.get(citation.evidence_id)
        if item is None or not item.source_type:
            raise ValueError("unknown or unproven legal evidence ID")
        if citation.source_citation is not None and citation.source_citation != item.source_citation:
            raise ValueError("legal citation metadata does not match retrieved provenance")
        if citation.quote is not None and citation.quote not in item.text:
            raise ValueError("quoted legal text is not present in retrieved evidence")
        seen.add(citation.evidence_id)
        verified.append(citation.model_copy(update={"source_citation": item.source_citation}))
    if analysis.evidence_gate.sufficient and not verified:
        raise ValueError("sufficient legal evidence requires at least one citation")
    return analysis.model_copy(update={"citations": verified})

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from typing import Any, cast

from app.services.contracts.schemas import (
    Clause,
    ClauseType,
    Confidentiality,
    ContractIntelligence,
    DateFact,
    GoverningLaw,
    Indemnification,
    IntellectualProperty,
    Liability,
    MetadataValue,
    NoticePeriod,
    Obligation,
    Party,
    Payment,
    Renewal,
    RestrictiveCovenant,
    Termination,
)
from app.services.generation.context import EvidenceItem

_DAYS = re.compile(r"\b(\d+)\s+(calendar\s+|business\s+)?days?\b", re.IGNORECASE)
_CLAUSE_TYPES: dict[str, ClauseType] = {
    "definition": ClauseType.definitions, "scope": ClauseType.scope, "service": ClauseType.services,
    "deliver": ClauseType.deliverables, "payment": ClauseType.payment, "fee": ClauseType.fees,
    "tax": ClauseType.taxes, "term": ClauseType.term, "renew": ClauseType.renewal,
    "terminat": ClauseType.termination, "notice": ClauseType.notice, "indemn": ClauseType.indemnification,
    "liability": ClauseType.limitation_of_liability, "confidential": ClauseType.confidentiality,
    "intellectual property": ClauseType.intellectual_property, "data protection": ClauseType.data_protection,
    "governing law": ClauseType.governing_law, "jurisdiction": ClauseType.jurisdiction,
    "arbitration": ClauseType.dispute_resolution, "assignment": ClauseType.assignment,
    "subcontract": ClauseType.subcontracting, "force majeure": ClauseType.force_majeure,
    "non-compete": ClauseType.non_compete, "non-solicit": ClauseType.non_solicit,
}


def _evidence(items: Iterable[EvidenceItem]) -> list[EvidenceItem]:
    return list(items)


def _refs(items: list[EvidenceItem]) -> tuple[list[str], float]:
    return [item.citation_id for item in items], 0.9 if items else 0.0


def _matches(items: list[EvidenceItem], *words: str) -> list[EvidenceItem]:
    return [item for item in items if any(word.lower() in item.text.lower() for word in words)]


def _type(title: str | None, text: str) -> ClauseType:
    value = f"{title or ''} {text}".lower()
    for key, result in _CLAUSE_TYPES.items():
        if key in value:
            if result == ClauseType.termination:
                if "convenience" in value: return ClauseType.termination_for_convenience
                if "cause" in value or "breach" in value: return ClauseType.termination_for_cause
            return result
    return ClauseType.unknown


def _period(text: str) -> tuple[int | None, str | None]:
    match = _DAYS.search(text)
    return (int(match.group(1)), (match.group(2) or "calendar ").strip()) if match else (None, None)


def extract_contract_facts(
    tenant_id: uuid.UUID, document_id: uuid.UUID, version_id: uuid.UUID, items: list[EvidenceItem],
) -> ContractIntelligence:
    clauses: list[Clause] = []
    for item in items:
        refs, confidence = _refs([item])
        clauses.append(Clause(clause_id=f"C{len(clauses)+1}", document_version_id=version_id,
            chunk_id=item.chunk_id, section=item.section_identifier, clause_number=item.clause_identifier,
            clause_title=item.clause_title or item.section_title, clause_type=_type(item.clause_title, item.text),
            text=item.text, physical_page_start=item.physical_page_start, physical_page_end=item.physical_page_end,
            source_blocks=item.source_block_provenance, evidence_ids=refs, confidence=confidence))

    party_items = _matches(items, "between", "party", "customer", "supplier", "vendor", "client")
    parties: list[Party] = []
    seen: set[str] = set()
    for item in party_items:
        for match in re.finditer(r"(?:between|party\s*[:\-])\s+([A-Z][\w .,&'-]{2,80}?)(?:\s+and\s+|,\s+|\s+\(|\s+shall\b)", item.text):
            name = match.group(1)
            normalized = name.strip(" ,.-")
            if normalized.lower() not in seen and len(normalized.split()) <= 12:
                seen.add(normalized.lower()); refs, conf = _refs([item])
                parties.append(Party(normalized_name=normalized, evidence_ids=refs, confidence=conf))
    # Common contract recital form: "Acme (Customer) and Beta (Supplier)"
    for item in party_items:
        for name, role in re.findall(r"([A-Z][\w .,&'-]{2,60})\s*\((Customer|Supplier|Vendor|Client|Party)\)", item.text, re.IGNORECASE):
            if name.lower() not in seen:
                seen.add(name.lower()); refs, conf = _refs([item]); parties.append(
                    Party(normalized_name=name.strip(), role=role, evidence_ids=refs, confidence=conf))

    notice_items = _matches(items, "notice", "prior written")
    notices: list[NoticePeriod] = []
    for item in notice_items:
        amount, unit = _period(item.text)
        if amount is not None:
            refs, conf = _refs([item]); notices.append(NoticePeriod(notice_period=amount, unit=unit,
                triggering_event="before expiration" if "expir" in item.text.lower() else "termination",
                notice_method="written" if "written" in item.text.lower() else None,
                original_expression=item.text, evidence_ids=refs, confidence=conf))

    renewal_items = _matches(items, "renew", "auto-renew")
    renewal = None
    if renewal_items:
        item = renewal_items[0]; refs, conf = _refs([item]); amount, unit = _period(item.text)
        renewal = Renewal(automatic=True if "automatic" in item.text.lower() or "auto" in item.text.lower() else None,
            renewal_period=(f"{amount} {unit}" if amount else ("one year" if "year" in item.text.lower() else None)),
            non_renewal_notice=notices[0] if "non-renew" in item.text.lower() or "cancel" in item.text.lower() else None,
            notice_deadline=item.text if "notice" in item.text.lower() else None, evidence_ids=refs, confidence=conf)

    term_items = _matches(items, "termination", "terminate")
    termination = None
    if term_items:
        item = term_items[0]; refs, conf = _refs([item]); amount, unit = _period(item.text)
        termination = Termination(termination_for_convenience="convenience" in item.text.lower(),
            termination_for_cause=any(x in item.text.lower() for x in ("cause", "breach", "default")),
            breach=item.text if "breach" in item.text.lower() else None,
            insolvency="insolv" in item.text.lower(), nonpayment="non-payment" in item.text.lower() or "nonpayment" in item.text.lower(),
            notice_requirement=f"{amount} {unit}" if amount else None,
            cure_period=(item.text if "cure" in item.text.lower() else None),
            termination_penalties=(item.text if "penalt" in item.text.lower() else None), evidence_ids=refs, confidence=conf)

    def one(cls: type[Any], words: tuple[str, ...]) -> Any:
        found = _matches(items, *words)
        if not found: return None
        item = found[0]; refs, conf = _refs([item]); return cls(evidence_ids=refs, confidence=conf)

    indemn = one(Indemnification, ("indemn",))
    if indemn:
        item = _matches(items, "indemn")[0]
        indemn.covered_claims = [item.text]
        indemn.third_party_claims = "third party" in item.text.lower()
    liability = one(Liability, ("liability", "liable"))
    if liability:
        item = _matches(items, "liability", "liable")[0]; lower = item.text.lower()
        liability.liability_cap = item.text if "cap" in lower or "limited" in lower else None
        amount_match = re.search(r"(?:inr|rs\.?|₹)\s*[\d,]+", item.text, re.IGNORECASE)
        liability.cap_amount = amount_match.group(0) if amount_match else None
        liability.cap_basis = item.text if "fees" in lower or "previous" in lower else None
        liability.consequential_damage_exclusion = "consequential" in lower
        liability.carveouts = [item.text] if "carveout" in lower or "except" in lower else []
        liability.uncapped_liabilities = [item.text] if "uncapped" in lower or "not limited" in lower else []
    payment = one(Payment, ("payment", "invoice", "fees"))
    if payment:
        item = _matches(items, "payment", "invoice", "fees")[0]; lower = item.text.lower()
        amount_match = re.search(r"(?:inr|rs\.?|₹)\s*[\d,]+", item.text, re.IGNORECASE)
        payment.amount = amount_match.group(0) if amount_match else None
        payment.currency = "INR" if amount_match and amount_match.group(0).lower().startswith(("inr", "rs", "₹")) else None
        payment.payment_deadline = item.text if _DAYS.search(item.text) else None
        payment.payment_schedule = item.text if any(x in lower for x in ("monthly", "quarterly", "annual", "milestone")) else None
        payment.late_fees = item.text if "late" in lower or "interest" in lower else None
        payment.taxes = item.text if "tax" in lower else None
    confidentiality = one(Confidentiality, ("confidential",))
    if confidentiality:
        item = _matches(items, "confidential")[0]; lower = item.text.lower()
        confidentiality.confidential_information_definition = item.text
        confidentiality.confidentiality_obligations = item.text if any(x in lower for x in ("shall", "must", "keep")) else None
        confidentiality.survival = item.text if "surviv" in lower else None
        confidentiality.duration = item.text if "year" in lower or "month" in lower else None
    ip = one(IntellectualProperty, ("intellectual property", "work product", "ownership"))
    if ip:
        item = _matches(items, "intellectual property", "work product", "ownership")[0]; lower = item.text.lower()
        ip.ownership = item.text if "own" in lower else None
        ip.assignment = item.text if "assign" in lower else None
        ip.work_product = item.text if "work product" in lower else None
    law = one(GoverningLaw, ("governing law", "jurisdiction", "court", "arbitration"))
    if law:
        item = _matches(items, "governing law", "jurisdiction", "court", "arbitration")[0]; lower = item.text.lower()
        law.governing_law = item.text if "govern" in lower else None
        law.jurisdiction = item.text if "jurisdiction" in lower else None
        law.courts = item.text if "court" in lower else None
        law.arbitration = item.text if "arbit" in lower else None
    covenants: list[RestrictiveCovenant] = []
    for item in _matches(items, "non-solicit", "non-solicitation", "non-compete"):
        kind = cast(Any, "non_compete" if "non-compete" in item.text.lower() else "non_solicit"); refs, conf = _refs([item])
        covenants.append(RestrictiveCovenant(covenant_type=kind, scope=item.text, restrictions=item.text,
                                             evidence_ids=refs, confidence=conf))

    dates: list[DateFact] = []
    for item in items:
        for expression in re.findall(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Z][a-z]+\s+\d{4}|[A-Z][a-z]+\s+\d{1,2},\s+\d{4})\b", item.text):
            refs, conf = _refs([item]); dates.append(DateFact(kind="date", original_expression=expression, evidence_ids=refs, confidence=conf))

    obligations: list[Obligation] = []
    for item in items:
        if re.search(r"\b(shall|must|required to|agrees to)\b", item.text, re.IGNORECASE):
            refs, conf = _refs([item]); obligations.append(Obligation(obligation_id=f"O{len(obligations)+1}", action=item.text,
                original_expression=item.text, deadline=item.text if _DAYS.search(item.text) else None,
                evidence_ids=refs, confidence=conf))

    metadata: dict[str, MetadataValue | None] = {}
    for key, value, found in (("effective_date", dates[0].original_expression if dates else None, items if dates else []),
                               ("contract_title", clauses[0].clause_title if clauses else None, items if clauses else [])):
        metadata[key] = None if value is None else MetadataValue(value=value, evidence_ids=[found[0].citation_id], confidence=.8)
    return ContractIntelligence(analysis_version="v1", document_id=document_id, document_version_id=version_id,
        tenant_id=tenant_id, clauses=clauses, parties=parties, obligations=obligations, dates=dates,
        notice_periods=notices, renewal=renewal, termination=termination, indemnification=indemn,
        limitation_of_liability=liability, payment=payment, confidentiality=confidentiality,
        intellectual_property=ip, governing_law=law, restrictive_covenants=covenants, metadata=metadata)

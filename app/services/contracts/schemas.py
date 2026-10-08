from __future__ import annotations

import enum
import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClauseType(str, enum.Enum):
    definitions = "definitions"; scope = "scope"; services = "services"; deliverables = "deliverables"
    payment = "payment"; fees = "fees"; taxes = "taxes"; term = "term"; renewal = "renewal"
    termination = "termination"; termination_for_convenience = "termination_for_convenience"
    termination_for_cause = "termination_for_cause"; notice = "notice"; indemnification = "indemnification"
    limitation_of_liability = "limitation_of_liability"; confidentiality = "confidentiality"
    intellectual_property = "intellectual_property"; data_protection = "data_protection"
    representations_and_warranties = "representations_and_warranties"; insurance = "insurance"
    audit = "audit"; compliance = "compliance"; governing_law = "governing_law"; jurisdiction = "jurisdiction"
    dispute_resolution = "dispute_resolution"; assignment = "assignment"; subcontracting = "subcontracting"
    force_majeure = "force_majeure"; non_compete = "non_compete"; non_solicit = "non_solicit"
    miscellaneous = "miscellaneous"; unknown = "unknown"; other = "other"


class Severity(str, enum.Enum):
    LOW = "LOW"; MEDIUM = "MEDIUM"; HIGH = "HIGH"; CRITICAL = "CRITICAL"


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class Clause(EvidenceRef):
    clause_id: str
    document_version_id: uuid.UUID
    chunk_id: uuid.UUID
    section: str | None = None
    clause_number: str | None = None
    clause_title: str | None = None
    clause_type: ClauseType = ClauseType.unknown
    text: str
    physical_page_start: int | None = None
    physical_page_end: int | None = None
    source_blocks: list[dict[str, object]] = Field(default_factory=list)


class Party(EvidenceRef):
    normalized_name: str
    role: str | None = None
    contractual: bool = True


class Obligation(EvidenceRef):
    obligation_id: str
    party: str | None = None
    action: str
    object: str | None = None
    trigger: str | None = None
    deadline: str | None = None
    recurrence: str | None = None
    conditions: list[str] = Field(default_factory=list)
    original_expression: str | None = None


class DateFact(EvidenceRef):
    kind: str
    original_expression: str
    normalized_date: date | None = None
    normalized_value: str | None = None


class NoticePeriod(EvidenceRef):
    notice_period: int | None = None
    unit: str | None = None
    triggering_event: str | None = None
    notice_method: str | None = None
    recipient: str | None = None
    original_expression: str


class Renewal(EvidenceRef):
    automatic: bool | None = None
    renewal_period: str | None = None
    number_of_renewals: int | None = None
    non_renewal_notice: NoticePeriod | None = None
    notice_deadline: str | None = None
    conditions: list[str] = Field(default_factory=list)


class Termination(EvidenceRef):
    termination_for_convenience: bool | None = None
    termination_for_cause: bool | None = None
    breach: str | None = None
    insolvency: bool | None = None
    nonpayment: bool | None = None
    notice_requirement: str | None = None
    cure_period: str | None = None
    termination_penalties: str | None = None
    post_termination_obligations: list[str] = Field(default_factory=list)
    survival: str | None = None


class Indemnification(EvidenceRef):
    indemnifying_party: str | None = None; indemnified_party: str | None = None
    covered_claims: list[str] = Field(default_factory=list); third_party_claims: bool | None = None
    exclusions: list[str] = Field(default_factory=list); defense_control: str | None = None
    caps: str | None = None; carveouts: list[str] = Field(default_factory=list); survival: str | None = None


class Liability(EvidenceRef):
    liability_cap: str | None = None; cap_basis: str | None = None; cap_amount: str | None = None
    cap_multiple: str | None = None; consequential_damage_exclusion: bool | None = None
    excluded_damages: list[str] = Field(default_factory=list); carveouts: list[str] = Field(default_factory=list)
    uncapped_liabilities: list[str] = Field(default_factory=list)


class Payment(EvidenceRef):
    amount: str | None = None; currency: str | None = None; payment_schedule: str | None = None
    invoice_requirements: str | None = None; payment_deadline: str | None = None; late_fees: str | None = None
    taxes: str | None = None; withholding: str | None = None; expenses: str | None = None
    milestones: list[str] = Field(default_factory=list)


class Confidentiality(EvidenceRef):
    confidential_information_definition: str | None = None; confidentiality_obligations: str | None = None
    permitted_disclosures: list[str] = Field(default_factory=list); exceptions: list[str] = Field(default_factory=list)
    duration: str | None = None; return_or_destruction: str | None = None; survival: str | None = None


class IntellectualProperty(EvidenceRef):
    background_ip: str | None = None; foreground_ip: str | None = None; ownership: str | None = None
    assignment: str | None = None; license: str | None = None; work_product: str | None = None
    derivatives: str | None = None; duration: str | None = None; territory: str | None = None
    sublicensing: str | None = None


class GoverningLaw(EvidenceRef):
    governing_law: str | None = None; jurisdiction: str | None = None; courts: str | None = None
    arbitration: str | None = None; dispute_resolution: str | None = None; seat_or_place: str | None = None


class RestrictiveCovenant(EvidenceRef):
    covenant_type: Literal["non_compete", "non_solicit"]
    parties: list[str] = Field(default_factory=list); scope: str | None = None; duration: str | None = None
    territory: str | None = None; restrictions: str | None = None


class MetadataValue(EvidenceRef):
    value: object


class RiskFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risk_id: str; risk_type: str; severity: Severity; title: str; description: str; reason: str
    evidence_ids: list[str] = Field(default_factory=list); source_metadata: dict[str, object] = Field(default_factory=dict)
    rule_id: str


class ContractIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_version: str
    document_id: uuid.UUID; document_version_id: uuid.UUID; tenant_id: uuid.UUID
    clauses: list[Clause] = Field(default_factory=list); parties: list[Party] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list); dates: list[DateFact] = Field(default_factory=list)
    notice_periods: list[NoticePeriod] = Field(default_factory=list); renewal: Renewal | None = None
    termination: Termination | None = None; indemnification: Indemnification | None = None
    limitation_of_liability: Liability | None = None; payment: Payment | None = None
    confidentiality: Confidentiality | None = None; intellectual_property: IntellectualProperty | None = None
    governing_law: GoverningLaw | None = None; restrictive_covenants: list[RestrictiveCovenant] = Field(default_factory=list)
    metadata: dict[str, MetadataValue | None] = Field(default_factory=dict)
    risks: list[RiskFinding] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    tenant_id: uuid.UUID | None = None

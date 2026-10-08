from __future__ import annotations

import re

from app.services.contracts.schemas import ContractIntelligence, RiskFinding, Severity


def evaluate_risks(
    facts: ContractIntelligence, *, short_renewal_notice_days: int = 30,
    long_termination_notice_days: int = 90, long_confidentiality_survival_years: int = 5,
) -> list[RiskFinding]:
    """Product-policy signals only; rules do not express legal conclusions."""
    findings: list[RiskFinding] = []

    def add(rule: str, kind: str, severity: Severity, title: str, description: str, reason: str, evidence: list[str]) -> None:
        if evidence:
            findings.append(RiskFinding(risk_id=f"R{len(findings)+1}", risk_type=kind, severity=severity,
                title=title, description=description, reason=reason, evidence_ids=evidence,
                source_metadata={"analysis_version": facts.analysis_version}, rule_id=rule))

    if facts.renewal and facts.renewal.automatic:
        add("RULE-RENEWAL-001", "automatic_renewal", Severity.MEDIUM, "Automatic renewal",
            "The agreement contains an automatic renewal condition.", "Automatic renewal is present in the extracted renewal clause.", facts.renewal.evidence_ids)
        notice = facts.renewal.non_renewal_notice
        if notice and notice.notice_period is not None and notice.notice_period <= short_renewal_notice_days:
            add("RULE-RENEWAL-002", "short_renewal_cancellation_window", Severity.MEDIUM, "Short renewal cancellation window",
                "The non-renewal notice window meets the configured short-window threshold.",
                f"{notice.notice_period} days is at or below the product threshold of {short_renewal_notice_days} days.", notice.evidence_ids)
    if facts.termination:
        match = re.search(r"(\d+)\s+days", facts.termination.notice_requirement or "", re.IGNORECASE)
        if match and int(match.group(1)) >= long_termination_notice_days:
            add("RULE-TERMINATION-001", "long_termination_notice", Severity.MEDIUM, "Long termination notice",
                "The extracted termination notice meets the configured long-notice threshold.",
                f"{match.group(1)} days is at or above {long_termination_notice_days} days.", facts.termination.evidence_ids)
        if facts.termination.termination_penalties:
            add("RULE-TERMINATION-002", "termination_penalty", Severity.HIGH, "Termination penalty",
                "The termination provision mentions a penalty or charge.", "Penalty language was found in termination evidence.", facts.termination.evidence_ids)
    if facts.limitation_of_liability:
        liability = facts.limitation_of_liability
        if liability.uncapped_liabilities:
            add("RULE-LIABILITY-001", "uncapped_liability", Severity.HIGH, "Uncapped liability",
                "The liability provision identifies uncapped liabilities.", "Uncapped liability language was extracted.", liability.evidence_ids)
        if liability.carveouts:
            add("RULE-LIABILITY-002", "liability_carveout", Severity.MEDIUM, "Liability carveout",
                "The liability cap contains carveout language.", "Carveout language was extracted from the liability provision.", liability.evidence_ids)
    if facts.confidentiality and facts.confidentiality.survival:
        match = re.search(r"(\d+)\s+years?", facts.confidentiality.survival, re.IGNORECASE)
        if match and int(match.group(1)) >= long_confidentiality_survival_years:
            add("RULE-CONFIDENTIALITY-001", "long_confidentiality_survival", Severity.MEDIUM,
                "Long confidentiality survival", "Confidentiality survival meets the configured threshold.",
                f"{match.group(1)} years is at or above {long_confidentiality_survival_years} years.", facts.confidentiality.evidence_ids)
    if facts.indemnification and facts.indemnification.covered_claims:
        add("RULE-INDEMNIFICATION-001", "broad_indemnification", Severity.MEDIUM,
            "Broad indemnification language", "The indemnification clause contains covered-claim language.",
            "The product flags the clause for review; scope and enforceability are not assessed.", facts.indemnification.evidence_ids)
    if facts.governing_law and facts.governing_law.jurisdiction:
        add("RULE-JURISDICTION-001", "explicit_jurisdiction", Severity.LOW, "Explicit jurisdiction",
            "The agreement names a jurisdiction or court.", "Jurisdiction language was extracted from the contract.", facts.governing_law.evidence_ids)
    if facts.intellectual_property and facts.intellectual_property.assignment:
        add("RULE-IP-001", "broad_ip_assignment", Severity.MEDIUM, "IP assignment identified",
            "The intellectual-property provision contains assignment language.",
            "The product flags assignment scope for review; ownership and enforceability are not inferred.", facts.intellectual_property.evidence_ids)
    if facts.payment and not facts.payment.payment_deadline:
        add("RULE-PAYMENT-001", "payment_risk", Severity.MEDIUM, "Payment deadline not identified",
            "Payment evidence was found but no explicit payment deadline was extracted.",
            "The available payment evidence does not contain a safely extracted deadline.", facts.payment.evidence_ids)
    if facts.obligations:
        undated = [item for item in facts.obligations if item.deadline is None]
        if undated:
            add("RULE-OBLIGATION-001", "material_obligation_without_deadline", Severity.LOW,
                "Obligation without clear deadline", "At least one obligation lacks a clear extracted deadline.",
                "The obligation expression contains no safely extracted time expression.", undated[0].evidence_ids)
    if facts.obligations and facts.parties and len(facts.parties) == 1:
        add("RULE-OBLIGATION-002", "one_sided_obligations", Severity.LOW, "One-sided obligation signal",
            "The available evidence identifies obligations and only one contractual party.",
            "This is a review signal, not a conclusion about commercial balance.", facts.obligations[0].evidence_ids)
    if facts.clauses and not facts.payment:
        add("RULE-CLAUSE-001", "missing_expected_clause", Severity.LOW, "Payment clause not identified",
            "No payment clause was identified in the available contract evidence.",
            "Payment is an expected product category but was not extracted; review the source.", facts.clauses[0].evidence_ids)
    if facts.restrictive_covenants:
        for covenant in facts.restrictive_covenants:
            add("RULE-RESTRICTIVE-001", "broad_restrictive_covenant", Severity.MEDIUM,
                "Restrictive covenant identified", "The agreement contains a selected restrictive covenant.",
                "Restrictive covenant text was extracted; enforceability is not assessed.", covenant.evidence_ids)
    return findings

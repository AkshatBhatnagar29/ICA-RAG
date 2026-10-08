from __future__ import annotations

import re
import uuid
from collections.abc import Callable

from app.services.contracts.schemas import ContractIntelligence
from app.services.legal.models import LegalQuery

_IDENTIFIER = re.compile(r"\b(?:section|article|clause|paragraph)\s+\d+(?:[.\w()/-]*)", re.IGNORECASE)


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(value.split())
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            output.append(normalized)
    return output


def build_deterministic_query(issue: str, intelligence: ContractIntelligence | None = None) -> str:
    """Build reproducible legal search terms from contract facts, not model memory."""
    terms = [issue]
    if intelligence is not None:
        for clause in intelligence.clauses:
            if clause.clause_title:
                terms.append(clause.clause_title)
            terms.append(clause.clause_type.value)
            terms.extend(_IDENTIFIER.findall(clause.text))
        terms.extend(r.risk_type for r in intelligence.risks)
        if intelligence.governing_law and intelligence.governing_law.governing_law:
            terms.append(intelligence.governing_law.governing_law)
        if intelligence.governing_law and intelligence.governing_law.jurisdiction:
            terms.append(intelligence.governing_law.jurisdiction)
    return " ".join(_unique(terms))[:4000]


def build_legal_query(
    issue: str,
    tenant_id: uuid.UUID,
    corpus_version_id: uuid.UUID,
    intelligence: ContractIntelligence | None = None,
    semantic_expander: Callable[[str], str] | None = None,
) -> LegalQuery:
    deterministic = build_deterministic_query(issue, intelligence)
    expansion = semantic_expander(deterministic) if semantic_expander else None
    text = " ".join(value for value in (deterministic, expansion) if value)
    return LegalQuery(text=text[:4000], deterministic_text=deterministic,
                      semantic_expansion=expansion, tenant_id=tenant_id,
                      corpus_version_id=corpus_version_id)

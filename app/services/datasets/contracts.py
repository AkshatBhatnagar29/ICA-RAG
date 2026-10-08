from __future__ import annotations

import csv
from pathlib import Path
from typing import TypedDict


class ContractClauseSample(TypedDict):
    source_dataset: str
    source_file: str
    source_row: int
    clause_text: str
    clause_type: str
    risk_level: str
    behavior: str


def select_contract_clauses(path: Path, clause_types: tuple[str, ...], limit_per_type: int = 1) -> list[ContractClauseSample]:
    """Select deterministic labeled clause examples without changing the raw CSV."""
    selected: list[ContractClauseSample] = []
    counts = {clause_type: 0 for clause_type in clause_types}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row_number, row in enumerate(csv.DictReader(stream), 2):
            clause_type = row["clause_type"]
            if clause_type not in counts or counts[clause_type] >= limit_per_type:
                continue
            selected.append({"source_dataset": "legal_contract_clauses",
                "source_file": str(path), "source_row": row_number,
                "clause_text": row["clause_text"], "clause_type": clause_type,
                "risk_level": row["risk_level"], "behavior": clause_type})
            counts[clause_type] += 1
            if all(count >= limit_per_type for count in counts.values()):
                break
    return selected


def select_contract_behaviors(
    path: Path, selections: tuple[tuple[str, str | None, str | None], ...]
) -> list[ContractClauseSample]:
    """Select labeled or text-backed behavior examples from the raw clause CSV."""
    wanted = {behavior: (clause_type, term) for behavior, clause_type, term in selections}
    selected: list[ContractClauseSample] = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row_number, row in enumerate(csv.DictReader(stream), 2):
            text = row["clause_text"]
            for behavior, (clause_type, term) in wanted.items():
                if any(item["behavior"] == behavior for item in selected):
                    continue
                label_match = clause_type is not None and row["clause_type"] == clause_type
                term_match = term is not None and term.lower() in text.lower()
                if label_match or term_match:
                    selected.append({"source_dataset": "legal_contract_clauses", "source_file": str(path),
                        "source_row": row_number, "clause_text": text, "clause_type": row["clause_type"],
                        "risk_level": row["risk_level"], "behavior": behavior})
    return selected

"""Derive a small provenance-preserving ICAT contract-clause sample."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.datasets.contracts import select_contract_behaviors

SOURCE = ROOT / "data/raw/contracts/legal_contract_clauses.csv"
OUTPUT = ROOT / "data/samples/contract_clause_sample_v1.json"
SELECTIONS = (("termination", "Termination For Convenience", None), ("renewal", "Renewal Term", None),
              ("liability_cap", "Cap On Liability", None), ("uncapped_liability", "Uncapped Liability", None),
              ("governing_law", "Governing Law", None), ("license", "License Grant", None),
              ("ip_assignment", "Ip Ownership Assignment", None), ("audit", "Audit Rights", None),
              ("anti_assignment", "Anti-Assignment", None), ("renewal_notice", "Notice Period To Terminate Renewal", None),
              ("payment", None, "payment"), ("indemnification", None, "indemn"),
              ("confidentiality", None, "confidential"), ("dispute_resolution", None, "arbitrat"))


def main() -> None:
    records = select_contract_behaviors(SOURCE, SELECTIONS)
    for record in records:
        record["source_file"] = str(Path(record["source_file"]).relative_to(ROOT))
    output = {"sample_version": "contract-clause-sample-v1", "source_dataset": str(SOURCE.relative_to(ROOT)),
              "selection": "first row for each labeled behavior or text-backed behavior", "records": records}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

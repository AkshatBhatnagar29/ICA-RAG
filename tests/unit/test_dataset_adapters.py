import uuid
from pathlib import Path

from app.services.datasets.contracts import select_contract_behaviors, select_contract_clauses
from app.services.datasets.legal import (
    map_case_law,
    map_legal_document,
    map_sample_record,
    stable_uuid,
)


def test_contract_adapter_selects_real_rows_with_provenance() -> None:
    path = Path("data/raw/contracts/legal_contract_clauses.csv")
    rows = select_contract_clauses(path, ("Termination For Convenience", "Renewal Term"))
    assert [row["clause_type"] for row in rows] == ["Renewal Term", "Termination For Convenience"]
    assert all(row["source_file"].endswith("legal_contract_clauses.csv") and row["source_row"] > 1 for row in rows)
    assert all(row["clause_text"].strip() for row in rows)


def test_contract_behavior_adapter_keeps_text_backed_provenance() -> None:
    rows = select_contract_behaviors(Path("data/raw/contracts/legal_contract_clauses.csv"),
        (("payment", None, "payment"), ("indemnification", None, "indemn")))
    assert [row["behavior"] for row in rows] == ["payment", "indemnification"]
    assert all(row["source_row"] > 1 and row["clause_type"] for row in rows)


def test_legal_mappings_preserve_source_identifiers() -> None:
    document = map_legal_document({"doc_id": "doc-1", "document_title": "Act", "document_type": "Act",
        "document_jurisdiction": "Central", "issuing_authority": "Parliament", "issue_date": "2020-01-02",
        "short_description": "summary", "text": "section text"}, source_file="train-00000.parquet")
    case = map_case_law({"case_metadata_id": "case-1", "case_title": "A v B", "indexable_text": "judgment",
        "neutral_citation": None, "law_report_citation": None, "docket_number": "D/1", "court_name": "High Court",
        "decision_date": "2020-01-03", "source_pdf_s3_url": "https://example.test/case.pdf",
        "parser_record_id": "parser-1", "source_relative_path": "year=2020/case.json", "source_filename": "case.json",
        "court_code": "HC"}, source_file="cases.parquet")
    assert document.source_identifier == "doc-1"
    assert document.effective_date is not None and document.effective_date.isoformat() == "2020-01-02"
    assert case.source_identifier == "case-1" and case.citation == "D/1"
    assert map_sample_record({"corpus": "indian-case-laws", "release": "sample-v1", "source_identifier": "case-1",
        "title": "A v B", "text": "judgment"}).source_type == "CASE_LAW"
    assert stable_uuid(uuid.UUID(int=1), "same") == stable_uuid(uuid.UUID(int=1), "same")

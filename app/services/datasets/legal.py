from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class LegalDatasetRecord:
    corpus_name: str
    release_identifier: str
    source_identifier: str
    title: str
    source_type: str
    text: str
    citation: str | None
    publisher: str | None
    jurisdiction: str | None
    source_uri: str | None
    effective_date: date | None
    metadata: dict[str, Any]


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def map_legal_document(row: dict[str, Any], *, source_file: str) -> LegalDatasetRecord:
    source_id = str(row["doc_id"])
    return LegalDatasetRecord("indian-legal-documents", "train-00000", source_id,
        str(row["document_title"]), str(row["document_type"] or "LEGAL_DOCUMENT"),
        str(row["text"]), None, str(row["issuing_authority"] or "") or None,
        str(row["document_jurisdiction"] or "") or None, None, _date(row.get("issue_date")),
        {"source_file": source_file, "source_doc_id": source_id,
         "short_description": row.get("short_description")})


def map_case_law(row: dict[str, Any], *, source_file: str) -> LegalDatasetRecord:
    source_id = str(row["case_metadata_id"])
    citation = row.get("neutral_citation") or row.get("law_report_citation") or row.get("docket_number")
    return LegalDatasetRecord("indian-case-laws", "sample-v1", source_id,
        str(row["case_title"]), "CASE_LAW", str(row["indexable_text"]), citation,
        str(row["court_name"] or "") or None, "India", row.get("source_pdf_s3_url"),
        _date(row.get("decision_date")),
        {"source_file": source_file, "case_metadata_id": source_id,
         "parser_record_id": row.get("parser_record_id"), "source_relative_path": row.get("source_relative_path"),
         "source_filename": row.get("source_filename"), "court_code": row.get("court_code")})


def map_sample_record(row: dict[str, Any]) -> LegalDatasetRecord:
    """Map the checked-in derived sample while retaining raw source provenance."""
    if row["corpus"] == "indian-case-laws":
        return LegalDatasetRecord("indian-case-laws", str(row["release"]), str(row["source_identifier"]),
            str(row["title"]), "CASE_LAW", str(row["text"]), row.get("citation"), row.get("publisher"),
            row.get("jurisdiction"), row.get("source_pdf_s3_url"), _date(row.get("effective_date")),
            {key: value for key, value in row.items() if key not in {"corpus", "release", "title", "text"}})
    return LegalDatasetRecord("indian-legal-documents", str(row["release"]), str(row["source_identifier"]),
        str(row["title"]), str(row.get("source_type") or "LEGAL_DOCUMENT"), str(row["text"]),
        row.get("citation"), row.get("publisher"), row.get("jurisdiction"), row.get("source_uri"),
        _date(row.get("effective_date")),
        {key: value for key, value in row.items() if key not in {"corpus", "release", "title", "text"}})


def stable_uuid(namespace: uuid.UUID, source_identifier: str) -> uuid.UUID:
    return uuid.uuid5(namespace, source_identifier)


def content_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

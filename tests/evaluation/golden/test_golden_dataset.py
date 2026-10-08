import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.evaluation.golden_dataset import GoldenDataset, load_golden_dataset

DATASET = Path(__file__).parents[3] / "data" / "evaluation" / "golden" / "standard_agreement_v2.json"


def test_expanded_dataset_has_pinned_provenance_and_unique_cases() -> None:
    dataset = load_golden_dataset(DATASET)
    assert len(dataset.cases) >= 50
    assert len({case.id for case in dataset.cases}) == len(dataset.cases)
    assert {case.document_version_id for case in dataset.cases} == {
        dataset.source_documents[0].document_version_id
    }


def test_legacy_shape_remains_separate_and_loadable() -> None:
    payload = {
        "dataset_name": "legacy",
        "version": "1.0",
        "description": "legacy fixture",
        "source_documents": [{
            "document_version_id": "d89c42a8-0cf3-489d-89a7-e76b3b12ced1",
            "source_document": "Standard-agreement.pdf",
            "source_sha256": "b720a8c0914608680f2001a0dc709b63c8f71ae0344e18809176962ebed37907",
            "provenance": "fixture",
        }],
        "cases": [{
            "id": "LEGACY-001", "category": "contract_factual", "question": "What is stated?",
            "document_version_id": "d89c42a8-0cf3-489d-89a7-e76b3b12ced1",
            "expected_answer": "The contract states a provision.", "expected_evidence": [],
            "minimum_citations": 0, "provenance": "fixture",
        }],
    }
    assert GoldenDataset.model_validate(json.loads(json.dumps(payload))).cases[0].id == "LEGACY-001"


def test_legal_case_requires_corpus_reference() -> None:
    with pytest.raises(ValidationError, match="legal_corpus_version_id"):
        GoldenDataset.model_validate({
            "dataset_name": "bad", "version": "1", "description": "bad",
            "source_documents": [{
                "document_version_id": "d89c42a8-0cf3-489d-89a7-e76b3b12ced1",
                "source_document": "x", "source_sha256": "0" * 64, "provenance": "x",
            }],
            "cases": [{
                "id": "BAD-001", "category": "legal_scope_required", "question": "Is this a legal question?",
                "document_version_id": "d89c42a8-0cf3-489d-89a7-e76b3b12ced1", "requires_legal": True,
                "expected_answer": "No conclusion.", "provenance": "x",
            }],
        })

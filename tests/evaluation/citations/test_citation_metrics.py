from app.services.evaluation.metrics import citation_precision, citation_recall


def test_citations_require_registry_membership() -> None:
    assert citation_precision(["E1", "E2"], ["E1"]) == 0.5
    assert citation_recall(["E1"], ["E1", "E2"]) == 0.5
    assert citation_precision(["E9"], ["E1"]) == 0.0

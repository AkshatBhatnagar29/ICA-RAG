from app.services.evaluation.golden_metrics import (
    citation_scores,
    concept_coverage,
    expected_evidence_found,
    forbidden_claims,
    limitation_present,
    recall_at_k,
    reciprocal_rank,
)


def evidence(page: int = 4) -> dict[str, object]:
    return {"evidence_id": "E1", "text": "The Official shall not bestow any right or claim to regular service.",
            "page_start": page, "chunk_id": "chunk-1"}


def test_golden_retrieval_anchor_metrics() -> None:
    expected = [{"page": 4, "anchor": "right or claim"}]
    results = [evidence()]
    assert expected_evidence_found(results, expected)
    assert recall_at_k(results, expected, 1) == 1.0
    assert reciprocal_rank(results, expected) == 1.0


def test_golden_citation_scoring_rejects_unknown_ids() -> None:
    scores = citation_scores(["E1", "E9"], [evidence()], [{"page": 4, "anchor": "right or claim"}])
    assert scores["correctness"] == 1.0
    assert scores["unsupported"] == 0.5


def test_golden_answer_guards() -> None:
    assert concept_coverage("The agreement requires written notice.", ["written notice"]) == 1.0
    assert concept_coverage("The agreement requires notice in writing.", ["written notice"]) == 1.0
    assert forbidden_claims("The agreement permits outside business.", ["outside business"])
    assert limitation_present("The exact salary cannot be determined from the blank placeholder.")

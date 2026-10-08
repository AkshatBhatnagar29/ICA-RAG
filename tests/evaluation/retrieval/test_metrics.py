from app.services.evaluation.metrics import (
    citation_precision,
    citation_recall,
    ndcg_at_k,
    percentile,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_ranking_metrics_are_hand_computable() -> None:
    retrieved = ["a", "x", "b"]
    assert recall_at_k(retrieved, ["a", "b"], 2) == 0.5
    assert precision_at_k(retrieved, ["a", "b"], 2) == 0.5
    assert reciprocal_rank(retrieved, ["b"]) == 1 / 3
    assert ndcg_at_k(retrieved, {"a": 1.0, "b": 1.0}, 3) > 0


def test_citation_metrics_and_percentile() -> None:
    assert citation_precision(["E1", "E9"], ["E1"]) == 0.5
    assert citation_recall(["E1"], ["E1", "E2"]) == 0.5
    assert percentile([1.0, 2.0, 3.0], 95) == 2.9

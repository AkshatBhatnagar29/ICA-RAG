from pathlib import Path

from app.services.evaluation.datasets import load_dataset
from app.services.evaluation.runner import evaluate_retrieval


def test_evaluation_is_deterministic_and_namespaces_corpora() -> None:
    dataset = load_dataset(Path("data/evaluation/retrieval/retrieval_v1.json"))
    first = evaluate_retrieval(dataset, 5)
    second = evaluate_retrieval(dataset, 5)
    first_metrics = first["methods"]["bm25"]["metrics"]
    second_metrics = second["methods"]["bm25"]["metrics"]
    assert first_metrics == second_metrics
    assert first["methods"].keys() == {"dense", "bm25", "hybrid", "hybrid_reranked"}

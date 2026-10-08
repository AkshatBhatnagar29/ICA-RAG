from pathlib import Path

from app.services.evaluation.datasets import load_dataset


def test_real_source_benchmark_preserves_provenance() -> None:
    dataset = load_dataset(Path("data/evaluation/retrieval/retrieval_v1.json"))
    assert dataset.dataset_version == "retrieval-v1"
    assert all(record.source_file.startswith("data/raw/") for record in dataset.records)
    assert {record.corpus for record in dataset.records} == {"contract", "legal"}

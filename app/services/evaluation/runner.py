from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.evaluation.metrics import (
    mean,
    ndcg_at_k,
    percentile,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.services.evaluation.models import EvaluationDataset, EvaluationRecord
from app.services.indexing.embeddings import LocalE5EmbeddingProvider
from app.services.reranking.service import LocalCrossEncoderReranker, RerankingError
from app.services.retrieval.bm25 import LocalBM25
from app.services.retrieval.fusion import reciprocal_rank_fusion
from app.services.retrieval.models import ChunkMetadata, DenseResult


def _candidate(row: EvaluationRecord) -> ChunkMetadata:
    return ChunkMetadata(uuid.uuid5(uuid.NAMESPACE_URL, row.record_id),
        uuid.uuid5(uuid.NAMESPACE_URL, row.source_dataset), uuid.uuid5(uuid.NAMESPACE_URL, row.record_id),
        row.text, None, None, None, row.metadata.get("section"), None, None, None, "CLAUSE", "DATASET", [],
        corpus=row.corpus)


def _ids(items: list[Any]) -> list[str]:
    return [str(item.metadata.chunk_id) for item in items]


def _metrics(samples: list[dict[str, Any]], dataset: EvaluationDataset) -> dict[str, object]:
    output: dict[str, object] = {}
    for method in ("dense", "bm25", "hybrid", "hybrid_reranked"):
        method_samples = [sample for sample in samples if sample["method"] == method]
        errors = [sample["error"] for sample in method_samples if sample["error"]]
        if errors and len(errors) == len(method_samples):
            output[method] = {"status": "unavailable", "error": errors[0]}
            continue
        per_k: dict[str, dict[str, float]] = {}
        for k in (1, 5, 10):
            recalls: list[float] = []
            precisions: list[float] = []
            mrrs: list[float] = []
            ndcgs: list[float] = []
            for record, sample in zip(dataset.records, method_samples, strict=True):
                expected = [str(uuid.uuid5(uuid.NAMESPACE_URL, item)) for item in record.expected_ids]
                relevance = {item: 1.0 for item in expected}
                ids = sample["ids"]
                recalls.append(recall_at_k(ids, expected, k))
                precisions.append(precision_at_k(ids, expected, k))
                mrrs.append(reciprocal_rank(ids, expected))
                ndcgs.append(ndcg_at_k(ids, relevance, k))
            per_k[f"k={k}"] = {"recall": mean(recalls), "precision": mean(precisions),
                                "mrr": mean(mrrs), "ndcg": mean(ndcgs)}
        latencies = [float(sample["latency_ms"]) for sample in method_samples]
        output[method] = {"status": "measured", "metrics": per_k,
                          "p50_latency_ms": percentile(latencies, 50),
                          "p95_latency_ms": percentile(latencies, 95),
                          "records": float(len(method_samples))}
    return output


def evaluate_retrieval(dataset: EvaluationDataset, top_k: int = 5) -> dict[str, object]:
    """Exercise the production embedding, BM25, RRF, and local reranker adapters."""
    rows = [_candidate(record) for record in dataset.records]
    settings = get_settings()
    provider = LocalE5EmbeddingProvider(settings)
    vectors = provider.embed_documents([row.text for row in rows])
    reranker = LocalCrossEncoderReranker(settings)
    samples: list[dict[str, Any]] = []
    for record in dataset.records:
        scoped = [(row, vector) for row, vector in zip(rows, vectors, strict=True)
                  if row.corpus == record.corpus]
        query_vector = provider.embed_query(record.query)
        dense_started = time.perf_counter()
        ranked = sorted(scoped, key=lambda pair: (-sum(a * b for a, b in zip(query_vector, pair[1], strict=True)),
                                                  str(pair[0].chunk_id)))
        dense = [DenseResult(row, sum(a * b for a, b in zip(query_vector, vector, strict=True)), rank)
                 for rank, (row, vector) in enumerate(ranked[:max(top_k, 10)], 1)]
        dense_latency = (time.perf_counter() - dense_started) * 1000
        sparse_started = time.perf_counter()
        sparse = LocalBM25().search(record.query, [row for row, _ in scoped], max(top_k, 10))
        sparse_latency = (time.perf_counter() - sparse_started) * 1000
        hybrid = reciprocal_rank_fusion(dense, sparse, max(top_k, 10))
        try:
            reranked = [item.result for item in reranker.rerank(record.query, hybrid)[:max(top_k, 10)]]
            rerank_error = None
        except RerankingError as exc:
            reranked = []
            rerank_error = str(exc)
        for method, items, latency, error in (
            ("dense", dense, dense_latency, None), ("bm25", sparse, sparse_latency, None),
            ("hybrid", hybrid, dense_latency + sparse_latency, None),
            ("hybrid_reranked", reranked, (reranker.last_latency_ms or 0.0), rerank_error),
        ):
            samples.append({"method": method, "ids": _ids(items), "latency_ms": latency, "error": error})
    return {"dataset_version": dataset.dataset_version,
            "label_quality": sorted({record.label_quality for record in dataset.records}),
            "methods": _metrics(samples, dataset), "embedding_provider": provider.provider,
            "embedding_model": provider.model, "reranker_model": reranker.model}


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

"""Run the frozen retrieval pipeline over a two-contract development set."""

from __future__ import annotations

import argparse
import asyncio
import json
import selectors
import sys
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import ResourceManager
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.services.evaluation.golden_metrics import recall_at_k
from app.services.indexing.embeddings import LocalE5EmbeddingProvider
from app.services.reranking.service import LocalCrossEncoderReranker, RerankingError
from app.services.retrieval.models import RetrievalMode, RetrievalQuery, RetrievalScope
from app.services.retrieval.service import RetrievalService
from scripts.evaluate_retrieval import aggregate, chunk_report, rows, score


def merge(paths: list[Path], output: Path) -> dict[str, Any]:
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    merged = {
        "dataset_name": "icia_two_contract_development_benchmark",
        "version": "v1",
        "description": "Combined frozen retrieval benchmark; source labels and cases are preserved.",
        "source_documents": [doc for payload in payloads for doc in payload["source_documents"]],
        "cases": [case for payload in payloads for case in payload["cases"]],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return merged


async def run(payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    provider = LocalE5EmbeddingProvider(settings)
    reranker = LocalCrossEncoderReranker(settings)
    retrieval = RetrievalService(provider, rrf_k=60, reranker=reranker)
    resources = ResourceManager(settings)
    methods = (("vector_only", RetrievalMode.DENSE, False), ("bm25", RetrievalMode.SPARSE, False))
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    chunks_by_version: dict[uuid.UUID, list[Chunk]] = {}
    tenants: dict[uuid.UUID, uuid.UUID] = {}
    async with resources.session_factory() as session:
        for source in payload["source_documents"]:
            version_id = uuid.UUID(source["document_version_id"])
            version = await session.get(DocumentVersion, version_id)
            document = await session.get(Document, version.document_id) if version else None
            if version is None or document is None or version.status != DocumentStatus.READY or document.tenant_id is None:
                raise ValueError(f"source version is not READY and tenant-scoped: {version_id}")
            tenants[version_id] = document.tenant_id
            chunks_by_version[version_id] = list((await session.execute(select(Chunk).where(
                Chunk.tenant_id == document.tenant_id, Chunk.document_version_id == version_id
            ).order_by(Chunk.chunk_index))).scalars().all())
        for case in payload["cases"]:
            if not case.get("retrieval_applicable", True):
                continue
            version_id = uuid.UUID(case["document_version_id"])
            tenant_id = tenants[version_id]
            expected = [dict(item) for item in case.get("expected_evidence", [])]
            for name, mode, rerank in methods:
                started = time.perf_counter()
                error = None
                response = None
                try:
                    response = await retrieval.search(session, RetrievalQuery(
                        query=case["question"],
                        scope=RetrievalScope(tenant_id=tenant_id, document_version_id=version_id),
                        top_k=10, mode=mode, rerank=rerank))
                except (RuntimeError, RerankingError) as exc:
                    error = f"{type(exc).__name__}: {exc}"
                elapsed = (time.perf_counter() - started) * 1000
                result_rows = rows(response.results) if response else []
                candidate_rows = rows(response.candidate_results) if response and response.candidate_results else result_rows
                samples[name].append({
                    "case_id": case["id"], "category": case.get("category"),
                    "document_version_id": str(version_id), "question": case["question"],
                    "scores": score(result_rows, case),
                    "candidate_scores": score(candidate_rows, case) | {"recall_at_40": recall_at_k(candidate_rows, expected, 40)},
                    "latency_ms": elapsed, "error": error, "results": result_rows,
                    "candidate_results": candidate_rows,
                })
            # Use one reranked call for the paired comparison. Its
            # candidate_results are the exact pre-rerank pool consumed by the
            # reranker, so both measurements have identical candidates.
            started = time.perf_counter()
            response = await retrieval.search(session, RetrievalQuery(
                query=case["question"],
                scope=RetrievalScope(tenant_id=tenant_id, document_version_id=version_id),
                top_k=10, mode=RetrievalMode.HYBRID, rerank=True))
            elapsed = (time.perf_counter() - started) * 1000
            candidate_rows = rows(response.candidate_results)
            baseline_rows = candidate_rows[:10]
            reranked_rows = rows(response.results)
            shared = {"case_id": case["id"], "category": case.get("category"),
                      "document_version_id": str(version_id), "question": case["question"],
                      "candidate_results": candidate_rows, "error": None}
            samples["hybrid"].append(shared | {
                "scores": score(baseline_rows, case),
                "candidate_scores": score(candidate_rows, case) | {"recall_at_40": recall_at_k(candidate_rows, expected, 40)},
                "latency_ms": max(0.0, elapsed - float(response.diagnostics.reranker_latency_ms or 0.0)),
                "results": baseline_rows,
            })
            samples["hybrid_reranked"].append(shared | {
                "scores": score(reranked_rows, case),
                "candidate_scores": score(candidate_rows, case) | {"recall_at_40": recall_at_k(candidate_rows, expected, 40)},
                "latency_ms": elapsed,
                "results": reranked_rows,
            })
    await resources.close()
    by_contract: dict[str, dict[str, dict[str, Any]]] = {}
    by_category: dict[str, dict[str, dict[str, Any]]] = {}
    for name, values in samples.items():
        contract_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        category_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for value in values:
            contract_groups[value["document_version_id"]].append(value)
            category_groups[f'{value["document_version_id"]}:{value["category"]}'].append(value)
        by_contract[name] = {key: aggregate(group) for key, group in contract_groups.items()}
        by_category[name] = {key: aggregate(group) for key, group in category_groups.items()}
    metrics = {name: aggregate(values) for name, values in samples.items()}
    return {
        "timestamp": datetime.now(UTC).isoformat(), "dataset": str(args.combined_dataset),
        "document_version_ids": [doc["document_version_id"] for doc in payload["source_documents"]],
        "total_cases": len(payload["cases"]),
        "retrieval_cases": sum(case.get("retrieval_applicable", True) for case in payload["cases"]),
        "excluded_cases": [case["id"] for case in payload["cases"] if not case.get("retrieval_applicable", True)],
        "metrics": metrics, "by_contract": by_contract, "by_category": by_category,
        "cases": dict(samples),
        "configuration": {"embedding_model": provider.model, "embedding_dimension": provider.dimension,
                          "reranker_model": reranker.model, "reranker_candidate_k": reranker.candidate_limit,
                          "rrf_k": 60, "dense_weight": 1.0, "sparse_weight": 1.0,
                          "chunk_refinement_mode": settings.chunk_refinement_mode,
                          "candidate_pool_identical_for_reranker": True},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract1", type=Path, required=True)
    parser.add_argument("--contract2", type=Path, required=True)
    parser.add_argument("--combined-dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = merge([args.contract1, args.contract2], args.combined_dataset)
    report = asyncio.run(run(payload, args), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

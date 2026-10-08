"""Measure production retrieval and reranking on the golden contract set.

The evaluator reports the vector/BM25/RRF candidate pool separately from the
reranked top-k. It never treats a generation failure as a retrieval failure.
"""

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
from statistics import median
from typing import Any

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import ResourceManager
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.services.evaluation.golden_metrics import (
    expected_evidence_found,
    first_relevant_rank,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.services.evaluation.metrics import percentile
from app.services.generation.context import build_evidence_packet
from app.services.indexing.embeddings import LocalE5EmbeddingProvider
from app.services.reranking.service import LocalCrossEncoderReranker, RerankingError
from app.services.retrieval.models import RetrievalMode, RetrievalQuery, RetrievalScope
from app.services.retrieval.service import RetrievalService


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [dict(item) for item in payload.get("cases", payload)]


def declared_version(path: Path) -> uuid.UUID | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents = payload.get("source_documents", [])
    if not documents:
        return None
    versions = {uuid.UUID(item["document_version_id"]) for item in documents}
    if len(versions) != 1:
        raise ValueError("retrieval evaluator currently requires one pinned contract version")
    return next(iter(versions))


async def resolve(session: Any, args: argparse.Namespace) -> tuple[uuid.UUID, uuid.UUID]:
    if args.document_version_id:
        version = await session.get(DocumentVersion, args.document_version_id)
        document = await session.get(Document, version.document_id) if version else None
    else:
        row = (await session.execute(select(DocumentVersion, Document).join(Document).where(
            DocumentVersion.original_filename.ilike(f"%{Path(args.source_document).stem}%"),
            DocumentVersion.status == DocumentStatus.READY,
        ).order_by(DocumentVersion.created_at.desc()))).first()
        version, document = row if row else (None, None)
    if version is None or document is None or version.status != DocumentStatus.READY or document.tenant_id is None:
        raise ValueError("a READY tenant-scoped document version is required")
    if args.tenant_id and args.tenant_id != document.tenant_id:
        raise ValueError("tenant does not match document")
    return document.tenant_id, version.id


def rows(results: list[Any]) -> list[dict[str, Any]]:
    return [{"evidence_id": f"R{rank}", "text": item.metadata.text,
             "page_start": item.metadata.physical_page_start, "page_end": item.metadata.physical_page_end,
             "chunk_id": str(item.metadata.chunk_id), "section": item.metadata.section_identifier,
             "clause": item.metadata.clause_number, "rank": rank,
             "dense_rank": item.dense_rank, "dense_score": item.dense_score,
             "sparse_rank": item.sparse_rank, "sparse_score": item.sparse_score,
             "rrf_score": item.rrf_score, "original_rank": item.original_rrf_rank}
            for rank, item in enumerate(results, 1)]


def score(items: list[dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    expected = [dict(item) for item in case.get("expected_evidence", [])]
    return {f"recall_at_{k}": recall_at_k(items, expected, k) for k in (1, 3, 5, 10)} | {
        "mrr": reciprocal_rank(items, expected),
        "ndcg_at_5": ndcg_at_k(items, expected, 5),
        "first_relevant_rank": first_relevant_rank(items, expected),
        "expected_found": expected_evidence_found(items, expected),
    }


def aggregate(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {"cases": 0}
    return {f"recall_at_{k}": sum(s["scores"][f"recall_at_{k}"] for s in samples) / len(samples)
            for k in (1, 3, 5, 10)} | {
        "mrr": sum(s["scores"]["mrr"] for s in samples) / len(samples),
        "ndcg_at_5": sum(s["scores"]["ndcg_at_5"] for s in samples) / len(samples),
        "candidate_recall_at_40": sum(s["candidate_scores"]["recall_at_40"] for s in samples) / len(samples),
        "mean_latency_ms": sum(s["latency_ms"] for s in samples) / len(samples),
        "p50_latency_ms": percentile([s["latency_ms"] for s in samples], 50),
        "p95_latency_ms": percentile([s["latency_ms"] for s in samples], 95),
        "cases": len(samples),
    }


def chunk_report(chunks: list[Chunk], cases: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [item.token_count for item in chunks]
    normalized = [" ".join(item.text.casefold().split()) for item in chunks]
    duplicates = len(normalized) - len(set(normalized))
    split = contained = adjacent = 0
    heading_together = 0
    for case in cases:
        for expected in case.get("expected_evidence", []):
            anchor = str(expected.get("anchor", "")).casefold()
            if not anchor:
                continue
            hits = [index for index, item in enumerate(chunks)
                    if anchor in " ".join(item.text.casefold().split())
                    and (expected.get("page") is None or expected["page"] in (item.physical_page_start, item.physical_page_end))]
            if hits:
                contained += 1
            else:
                page_hits = [index for index, item in enumerate(chunks) if anchor in " ".join(item.text.casefold().split())]
                if page_hits:
                    split += 1
                    if any(abs(left - right) == 1 for left in page_hits for right in page_hits if left != right):
                        adjacent += 1
            if hits and chunks[hits[0]].section_title and chunks[hits[0]].clause_number:
                heading_together += 1
    expected_count = sum(len(case.get("expected_evidence", [])) for case in cases)
    return {
        "documents": 1,
        "pages": len({page for item in chunks for page in (item.physical_page_start, item.physical_page_end) if page is not None}),
        "chunks": len(chunks),
        "average_tokens": sum(lengths) / len(lengths) if lengths else 0,
        "median_tokens": median(lengths) if lengths else 0,
        "min_tokens": min(lengths) if lengths else 0,
        "max_tokens": max(lengths) if lengths else 0,
        "very_small_chunks_lt_50": sum(value < 50 for value in lengths),
        "very_small_chunks_lt_25": sum(value < 25 for value in lengths),
        "small_chunks_lt_80": sum(value < 80 for value in lengths),
        "small_chunks_lt_100": sum(value < 100 for value in lengths),
        "extremely_large_chunks_gt_1000": sum(value > 1000 for value in lengths),
        "duplicate_text_ratio": duplicates / len(chunks) if chunks else 0,
        "expected_evidence_count": expected_count,
        "evidence_fully_contained_rate": contained / expected_count if expected_count else None,
        "evidence_split_rate": split / expected_count if expected_count else None,
        "adjacent_retrieval_required_rate": adjacent / expected_count if expected_count else None,
        "heading_clause_cohesion_rate": heading_together / expected_count if expected_count else None,
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    cases = load_cases(args.dataset)
    declared = declared_version(args.dataset)
    if declared and args.document_version_id and declared != args.document_version_id:
        raise ValueError("--document-version-id does not match the dataset's pinned version")
    if args.limit:
        cases = cases[:args.limit]
    settings = get_settings()
    provider = LocalE5EmbeddingProvider(settings)
    reranker = LocalCrossEncoderReranker(settings)
    retrieval = RetrievalService(provider, rrf_k=args.rrf_k, reranker=reranker,
                                 dense_weight=args.dense_weight, sparse_weight=args.sparse_weight)
    resources = ResourceManager(settings)
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_chunks: list[Chunk] = []
    async with resources.session_factory() as session:
        tenant, version = await resolve(session, args)
        if declared and version != declared:
            raise ValueError("resolved database version does not match the dataset's pinned version")
        all_chunks = list((await session.execute(select(Chunk).where(
            Chunk.tenant_id == tenant, Chunk.document_version_id == version).order_by(Chunk.chunk_index))).scalars().all())
        for case in cases:
            if not case.get("retrieval_applicable", True):
                continue
            expected = [dict(item) for item in case.get("expected_evidence", [])]
            methods = (
                ("vector_only", RetrievalMode.DENSE, False, 10),
                ("bm25", RetrievalMode.SPARSE, False, 10),
                ("hybrid", RetrievalMode.HYBRID, False, 10),
            )
            if not args.skip_reranker:
                methods += (("hybrid_reranked", RetrievalMode.HYBRID, True, 10),)
            for name, mode, rerank, top_k in methods:
                started = time.perf_counter()
                error = None
                response = None
                try:
                    response = await retrieval.search(session, RetrievalQuery(
                        query=case["question"], scope=RetrievalScope(tenant_id=tenant, document_version_id=version),
                        top_k=top_k, mode=mode, rerank=rerank))
                except (RuntimeError, RerankingError) as exc:
                    error = f"{type(exc).__name__}: {exc}"
                elapsed = (time.perf_counter() - started) * 1000
                result_rows = rows(response.results) if response else []
                candidate_rows = (rows(response.candidate_results) if response and response.candidate_results
                                  else result_rows)
                context = None
                if response:
                    packet = build_evidence_packet(
                        response.results,
                        settings.generation_max_context_tokens,
                        RetrievalScope(tenant_id=tenant, document_version_id=version),
                    )
                    context = {"evidence_count": len(packet.items),
                               "truncated_count": packet.truncated_count,
                               "context_tokens_estimate": len(packet.context) // 4}
                samples[name].append({"case_id": case["id"], "category": case.get("category"),
                                      "question": case["question"], "scores": score(result_rows, case),
                                      "candidate_scores": score(candidate_rows, case) | {
                                          "recall_at_40": recall_at_k(candidate_rows, expected, 40)
                                      }, "latency_ms": elapsed,
                                      "error": error, "results": result_rows,
                                      "candidate_results": candidate_rows,
                                      "context": context})
    await resources.close()
    metrics = {name: aggregate(values) for name, values in samples.items()}
    by_category: dict[str, dict[str, Any]] = {}
    for name, values in samples.items():
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for value in values:
            groups[value["category"] or "uncategorized"].append(value)
        by_category[name] = {category: aggregate(group) for category, group in groups.items()}
    return {"timestamp": datetime.now(UTC).isoformat(), "dataset": str(args.dataset),
            "document_version_id": str(version), "total_cases": len(cases),
            "retrieval_cases": sum(1 for case in cases if case.get("retrieval_applicable", True)),
            "excluded_cases": [case["id"] for case in cases if not case.get("retrieval_applicable", True)],
            "metrics": metrics, "by_category": by_category,
            "cases": {name: values for name, values in samples.items()},
            "chunking": chunk_report(all_chunks, cases),
            "configuration": {"embedding_model": provider.model, "embedding_dimension": provider.dimension,
                              "reranker_model": reranker.model, "reranker_max_length": reranker.max_length,
                              "reranker_candidate_k": reranker.candidate_limit, "rrf_k": args.rrf_k,
                              "dense_weight": args.dense_weight, "sparse_weight": args.sparse_weight,
                              "chunk_refinement_mode": settings.chunk_refinement_mode,
                              "experiment_name": args.experiment_name}}


def write(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "retrieval_report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    reranker = {"configuration": report["configuration"], "before": report["metrics"].get("hybrid"),
                "after": report["metrics"].get("hybrid_reranked"),
                "cases": report["cases"].get("hybrid_reranked", [])}
    (output_dir / "reranker_report.json").write_text(json.dumps(reranker, indent=2, default=str) + "\n", encoding="utf-8")
    (output_dir / "pipeline_comparison.json").write_text(json.dumps(report["metrics"], indent=2, default=str) + "\n", encoding="utf-8")
    (output_dir / "chunking_report.json").write_text(json.dumps(report["chunking"], indent=2, default=str) + "\n", encoding="utf-8")
    lines = ["# ICIA RAG baseline", "", f"Document version: `{report['document_version_id']}`", "", "## Retrieval", ""]
    for name, metrics in report["metrics"].items():
        lines.append(f"- **{name}**: Recall@1={metrics.get('recall_at_1', 0):.3f}, Recall@5={metrics.get('recall_at_5', 0):.3f}, MRR={metrics.get('mrr', 0):.3f}, mean latency={metrics.get('mean_latency_ms', 0):.1f} ms")
    lines.extend(["", "## Chunking", "", "```json", json.dumps(report["chunking"], indent=2), "```", ""])
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/evaluation/golden/standard_agreement_v1.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/evaluation/results")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--source-document", default="Standard-agreement.pdf")
    parser.add_argument("--document-version-id", type=uuid.UUID)
    parser.add_argument("--tenant-id", type=uuid.UUID)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--dense-weight", type=float, default=1.0)
    parser.add_argument("--sparse-weight", type=float, default=1.0)
    parser.add_argument("--experiment-name", default="baseline")
    parser.add_argument("--skip-reranker", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(run(args), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    write(report, args.output_dir)
    print(json.dumps(report["metrics"], indent=2, default=str))
    print(f"Reports: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

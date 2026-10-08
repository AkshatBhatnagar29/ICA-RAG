"""Run the real Ask ICIA pipeline against the checked-in golden dataset."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import selectors
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import ResourceManager
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.models.legal import LegalCorpusVersion
from app.services.agents.models import AgentRequest
from app.services.agents.service import AgentService
from app.services.contracts.comparison_service import ContractComparisonService
from app.services.contracts.service import ContractAnalysisService
from app.services.evaluation.golden_metrics import (
    citation_scores,
    concept_coverage,
    expected_evidence_found,
    first_relevant_rank,
    forbidden_claims,
    limitation_present,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.services.generation.llm import GroqProvider
from app.services.indexing.embeddings import LocalE5EmbeddingProvider
from app.services.ingestion.storage import LocalObjectStorage
from app.services.legal.retrieval import LegalRetrievalService
from app.services.reranking.service import LocalCrossEncoderReranker
from app.services.retrieval.models import RetrievalMode, RetrievalQuery, RetrievalScope
from app.services.retrieval.service import RetrievalService

REQUEST_DELAY_SECONDS = 20


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", payload)
    if not isinstance(cases, list):
        raise TypeError("golden dataset must contain a cases array")
    return [dict(case) for case in cases]


def dataset_version(path: Path) -> uuid.UUID | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents = payload.get("source_documents", [])
    if not documents:
        return None
    versions = {uuid.UUID(item["document_version_id"]) for item in documents}
    if len(versions) != 1:
        raise ValueError("golden runner requires one pinned contract version")
    return next(iter(versions))


def dataset_corpus(path: Path) -> uuid.UUID | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    versions = payload.get("legal_corpus_versions", [])
    return uuid.UUID(versions[0]) if len(versions) == 1 else None


async def resolve_ids(session: Any, source_document: str, version_id: uuid.UUID | None,
                     tenant_id: uuid.UUID | None, corpus_id: uuid.UUID | None,
                     needs_legal: bool) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]:
    if version_id is not None:
        version = await session.get(DocumentVersion, version_id)
        if version is None or version.status != DocumentStatus.READY:
            raise ValueError("document version must exist and be READY")
        document = await session.get(Document, version.document_id)
    else:
        result = await session.execute(select(DocumentVersion, Document).join(Document).where(
            DocumentVersion.original_filename.ilike(f"%{Path(source_document).stem}%"),
            DocumentVersion.status == DocumentStatus.READY).order_by(DocumentVersion.created_at.desc()))
        row = result.first()
        if row is None:
            raise ValueError(f"no READY document found for {source_document!r}; use --document-version-id")
        version, document = row
    if document is None or document.tenant_id is None:
        raise ValueError("evaluation document has no tenant scope")
    if tenant_id is not None and tenant_id != document.tenant_id:
        raise ValueError("--tenant-id does not match the evaluation document")
    if needs_legal and corpus_id is None:
        corpus = await session.scalar(select(LegalCorpusVersion).order_by(LegalCorpusVersion.created_at.desc()))
        corpus_id = corpus.id if corpus else None
    return document.tenant_id, version.id, corpus_id


def evidence_rows(response: Any) -> list[dict[str, Any]]:
    rows = response.execution_summary.get("evidence", [])
    return [dict(row, rank=rank) for rank, row in enumerate(rows, 1) if isinstance(row, dict)]


def metadata_rows(results: list[Any]) -> list[dict[str, Any]]:
    return [{"text": item.metadata.text, "page_start": item.metadata.physical_page_start,
             "page_end": item.metadata.physical_page_end, "chunk_id": str(item.metadata.chunk_id),
             "rank": rank, "dense_rank": item.dense_rank, "sparse_rank": item.sparse_rank,
             "dense_score": item.dense_score, "sparse_score": item.sparse_score,
             "rrf_score": item.rrf_score, "reranker_score": item.reranker_score,
             "original_rank": item.original_rrf_rank}
            for rank, item in enumerate(results, 1)]


async def measure_retrieval_methods(session: Any, retrieval: RetrievalService, tenant: uuid.UUID,
                                    version: uuid.UUID, cases: list[dict[str, Any]]) -> dict[str, Any]:
    methods = [RetrievalMode.DENSE, RetrievalMode.SPARSE, RetrievalMode.HYBRID]
    if retrieval.reranker is not None:
        methods.append(RetrievalMode.HYBRID)
    output: dict[str, Any] = {}
    diagnostics: list[dict[str, Any]] = []
    for index, mode in enumerate(methods):
        name = "hybrid_reranked" if index == 3 else mode.value
        samples: list[dict[str, Any]] = []
        for case in cases:
            if not case.get("retrieval_applicable", True):
                continue
            response = await retrieval.search(session, RetrievalQuery(
                query=case["question"],
                scope=RetrievalScope(tenant_id=tenant, document_version_id=version),
                top_k=10, mode=mode, rerank=index == 3))
            rows = metadata_rows(response.results)
            candidate_rows = metadata_rows(response.candidate_results)
            expected = [dict(item) for item in case.get("expected_evidence", [])]
            samples.append({"recall": {str(k): recall_at_k(rows, expected, k) for k in (1, 3, 5, 10)},
                            "mrr": reciprocal_rank(rows, expected),
                            "ndcg": {str(k): ndcg_at_k(rows, expected, k) for k in (5, 10)},
                            "candidate_recall": recall_at_k(candidate_rows, expected, 40) if candidate_rows else None})
            diagnostics.append({"case_id": case["id"], "method": name, "expected_evidence": expected,
                                "results": rows, "candidate_pool": candidate_rows,
                                "expected_found": expected_evidence_found(rows, expected)})
        output[name] = {f"recall_at_{k}": sum(item["recall"][str(k)] for item in samples) / len(samples)
                        for k in (1, 3, 5, 10)} | {
                            "mrr": sum(item["mrr"] for item in samples) / len(samples),
                            "ndcg_at_5": sum(item["ndcg"]["5"] for item in samples) / len(samples),
                            "ndcg_at_10": sum(item["ndcg"]["10"] for item in samples) / len(samples),
                            "candidate_recall_at_40": (sum(item["candidate_recall"] for item in samples
                                                            if item["candidate_recall"] is not None) /
                                                        sum(item["candidate_recall"] is not None for item in samples)
                                                        if any(item["candidate_recall"] is not None for item in samples)
                                                        else None),
                            "cases": len(samples)}
    return {"metrics": output, "cases": diagnostics}


def evaluate_case(case: dict[str, Any], response: Any, latency_ms: float, error: str | None = None,
                  *, llm_enabled: bool = True) -> dict[str, Any]:
    evidence = evidence_rows(response) if response else []
    contract = [item for item in evidence if item.get("domain") == "contract"]
    legal = [item for item in evidence if item.get("domain") == "legal"]
    expected = [dict(item) for item in case.get("expected_evidence", [])]
    answer = response.answer if response and llm_enabled else ""
    citations = list(response.citations) if response and llm_enabled else []
    citation = citation_scores(citations, evidence, expected)
    concepts = concept_coverage(answer, case.get("expected_concepts", []))
    forbidden = forbidden_claims(answer, case.get("forbidden_claims", []))
    contract_required = bool(case.get("requires_contract"))
    legal_required = bool(case.get("requires_legal"))
    insufficient = case.get("category") == "insufficient_evidence"
    legal_queried = bool(response and "legal_search" in response.execution_summary.get("tools", []))
    legal_scope = (not legal_required) or (legal_queried and bool(legal) and any(c.startswith("L") for c in citations))
    evidence_found = expected_evidence_found(contract, expected)
    grounded = bool(answer) and (not contract_required or evidence_found or insufficient) and not forbidden
    diagnostics = []
    if response:
        diagnostics.extend(response.warnings)
        synthesis_diagnostic = response.execution_summary.get("synthesis_diagnostic")
        if synthesis_diagnostic:
            diagnostics.append(f"synthesis_diagnostic: {synthesis_diagnostic}")
    if not llm_enabled:
        diagnostics.append("generation skipped: --no-llm")
    if insufficient:
        insufficient_ok = limitation_present(answer) and not any(char.isdigit() for char in answer)
    else:
        insufficient_ok = True
    provider_error = any(item.startswith(("final synthesis failed:", "synthesis_diagnostic:")) for item in diagnostics)
    answer_correct = concepts >= 1.0 and not forbidden
    if insufficient:
        answer_correct = insufficient_ok
    applicable = ([
        answer_correct, not forbidden, (not contract_required or evidence_found or insufficient),
        citation["count"] >= int(case.get("minimum_citations", 0)), grounded, legal_scope, insufficient_ok,
    ] if llm_enabled else [not contract_required or evidence_found or insufficient])
    status = ("ERROR" if error or provider_error else
              "RETRIEVAL_ONLY" if not llm_enabled else
              "PASS" if all(applicable) else "FAIL")
    failures: list[str] = []
    if error: failures.append("system error: " + error)
    if llm_enabled and not provider_error and not answer_correct: failures.append("answer concepts or expected limitation not satisfied")
    if llm_enabled and not provider_error and forbidden: failures.append("forbidden claim: " + "; ".join(forbidden))
    if contract_required and not evidence_found and not insufficient: failures.append("expected contract evidence not retrieved")
    if llm_enabled and not provider_error and citation["count"] < int(case.get("minimum_citations", 0)): failures.append("minimum citation count not met")
    if llm_enabled and not provider_error and not grounded: failures.append("answer is not grounded in returned evidence")
    if not legal_scope: failures.append("legal scope requirement not satisfied")
    if llm_enabled:
        failures.extend(f"generation: {item}" for item in diagnostics if item not in failures)
    return {
        "case_id": case["id"], "question": case["question"], "status": status,
        "retrieval": {"results": contract, "expected_evidence_found": evidence_found,
                       "first_relevant_rank": first_relevant_rank(contract, expected),
                       "recall_at": {str(k): recall_at_k(contract, expected, k) for k in (1, 3, 5, 10)}},
        "reranking": {"results": []},
        "generation": {"answer": answer, "latency_ms": round(latency_ms, 3),
                        "evaluated": llm_enabled, "diagnostics": diagnostics},
        "citations": {"returned": citations, **citation},
        "legal_context": {"required": legal_required, "queried": legal_queried, "used": bool(legal), "sources": legal},
        "scores": {"answer_correct": answer_correct if llm_enabled else None,
                   "grounded": grounded if llm_enabled else None,
                   "citation_coverage": citation["coverage"] if llm_enabled else None,
                   "citation_correct": citation["correctness"] if llm_enabled else None,
                   "citation_presence": citation["presence"] if llm_enabled else None,
                   "unsupported_citation": citation["unsupported"] if llm_enabled else None,
                   "legal_scope_compliance": legal_scope, "insufficient_evidence_handling": insufficient_ok,
                   "unsupported_claim": bool(forbidden)},
        "failure_reasons": failures,
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    cases = load_cases(args.dataset)
    pinned_version = dataset_version(args.dataset)
    pinned_corpus = dataset_corpus(args.dataset)
    if pinned_version and args.document_version_id and pinned_version != args.document_version_id:
        raise ValueError("--document-version-id does not match the dataset's pinned version")
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        raise ValueError("no golden cases selected")
    settings = get_settings()
    resources = ResourceManager(settings)
    provider = None if args.no_llm else GroqProvider(settings)
    embedder = LocalE5EmbeddingProvider(settings)
    reranker = LocalCrossEncoderReranker(settings) if settings.reranker_enabled else None
    retrieval = RetrievalService(embedder, reranker=reranker)
    legal = LegalRetrievalService(embedder, reranker=reranker)
    results: list[dict[str, Any]] = []
    async with resources.session_factory() as session:
        tenant, version, corpus = await resolve_ids(session, args.source_document, pinned_version or args.document_version_id,
                                                    args.tenant_id, args.corpus_version_id,
                                                    any(case.get("requires_legal") for case in cases))
        if pinned_corpus and args.corpus_version_id and pinned_corpus != args.corpus_version_id:
            raise ValueError("--corpus-version-id does not match the dataset's pinned corpus")
        if pinned_corpus:
            corpus = pinned_corpus
        retrieval_methods = await measure_retrieval_methods(session, retrieval, tenant, version, cases)
        for case_index, case in enumerate(cases):
            if case_index and not args.no_llm:
                await asyncio.sleep(REQUEST_DELAY_SECONDS)
            started = time.perf_counter()
            response = None
            error = None
            try:
                response = await AgentService(session, retrieval,
                    ContractAnalysisService(LocalObjectStorage(Path(settings.local_storage_root))),
                    ContractComparisonService(), legal, provider).run(AgentRequest(
                        query=case["question"], tenant_id=tenant, document_version_id=version,
                        corpus_version_id=corpus))
            except Exception as exc:  # noqa: BLE001 - case-level isolation is part of the report contract
                error = f"{type(exc).__name__}: {exc}"
            results.append(evaluate_case(case, response, (time.perf_counter() - started) * 1000, error,
                                         llm_enabled=not args.no_llm))
    await resources.close()
    return build_report(results, args.dataset, retrieval_methods)


def build_report(results: list[dict[str, Any]], dataset: Path,
                 retrieval_methods: dict[str, Any] | None = None) -> dict[str, Any]:
    latencies = [float(item["generation"]["latency_ms"]) for item in results]
    passed = sum(item["status"] == "PASS" for item in results)
    retrieval_only = sum(item["status"] == "RETRIEVAL_ONLY" for item in results)
    failed = sum(item["status"] == "FAIL" for item in results)
    errors = sum(item["status"] == "ERROR" for item in results)
    def mean(key: str) -> float | None:
        values = [float(item["scores"][key]) for item in results if item["scores"].get(key) is not None]
        return sum(values) / len(values) if values else None
    ordered = sorted(latencies)
    percentile = lambda p: ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p))] if ordered else 0.0
    retrieval = lambda k: sum(float(item["retrieval"]["recall_at"][str(k)]) for item in results) / len(results)
    llm_enabled = any(item["generation"].get("evaluated") for item in results)
    return {"timestamp": datetime.now(UTC).isoformat(), "dataset": str(dataset), "llm_enabled": llm_enabled,
            "total_cases": len(results),
            "passed": passed, "failed": failed, "errors": errors, "retrieval_only": retrieval_only,
            "end_to_end_pass_rate": passed / len(results) if llm_enabled else None,
            "retrieval_pass_rate": sum(item["retrieval"]["expected_evidence_found"] for item in results) / len(results),
            "retrieval_methods": (retrieval_methods or {}).get("metrics", {}),
            "retrieval_diagnostics": (retrieval_methods or {}).get("cases", []),
            "metrics": {"answer_accuracy": mean("answer_correct"), "groundedness": mean("grounded"),
                        "forbidden_claim_rate": mean("unsupported_claim"), "unsupported_claim_rate": mean("unsupported_claim"),
                        "recall_at_1": retrieval(1), "recall_at_3": retrieval(3), "recall_at_5": retrieval(5),
                        "recall_at_10": retrieval(10), "mrr": sum(float(item["retrieval"]["first_relevant_rank"] and
                            1 / item["retrieval"]["first_relevant_rank"] or 0) for item in results) / len(results),
                        "citation_coverage": mean("citation_coverage"), "citation_correctness": mean("citation_correct"),
                        "citation_presence_rate": mean("citation_presence"), "unsupported_citation_rate": mean("unsupported_citation"),
                        "legal_scope_compliance_rate": mean("legal_scope_compliance"),
                        "insufficient_evidence_handling_accuracy": mean("insufficient_evidence_handling"),
                        "average_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
                        "p50_latency_ms": percentile(.50), "p95_latency_ms": percentile(.95)},
            "cases": results}


def write_reports(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"golden_eval_{stamp}.json"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    (output_dir / "latest.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    lines = ["# ICIA Golden RAG Evaluation", "", f"- Total: {report['total_cases']}", f"- Passed: {report['passed']}",
             f"- Failed: {report['failed']}", f"- Errors: {report['errors']}",
             f"- Retrieval-only: {report['retrieval_only']}",
             f"- Retrieval evidence pass rate: {report['retrieval_pass_rate']:.4f}", "", "## Metrics", ""]
    lines.extend(f"- {key}: {value:.4f}" for key, value in report["metrics"].items() if isinstance(value, float))
    for case in report["cases"]:
        if case["status"] != "PASS":
            lines.extend(["", f"## {case['case_id']}", "", case["question"], "", "Failures: " + "; ".join(case["failure_reasons"])])
    (output_dir / f"golden_eval_{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (output_dir / f"golden_eval_{stamp}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "status", "latency_ms", "failure_reasons"])
        writer.writeheader()
        for case in report["cases"]:
            writer.writerow({"case_id": case["case_id"], "status": case["status"],
                             "latency_ms": case["generation"]["latency_ms"],
                             "failure_reasons": " | ".join(case["failure_reasons"])})
    citation_cases = [item for item in report["cases"] if item["generation"].get("evaluated")]
    citation_metrics = {key: (sum(float(item["scores"].get(source) or 0.0) for item in citation_cases) /
                              len(citation_cases) if citation_cases else None)
                        for key, source in (("presence", "citation_presence"),
                                            ("correctness", "citation_correct"),
                                            ("coverage", "citation_coverage"),
                                            ("unsupported_rate", "unsupported_citation"))}
    (output_dir / "citation_report.json").write_text(json.dumps({
        "timestamp": report["timestamp"], "evaluated_cases": len(citation_cases),
        "metrics": citation_metrics,
        "cases": [{"case_id": item["case_id"], "citations": item["citations"],
                   "scores": item["scores"]} for item in citation_cases],
    }, indent=2, default=str) + "\n", encoding="utf-8")
    (output_dir / "generation_report.json").write_text(json.dumps({
        "timestamp": report["timestamp"], "llm_enabled": report["llm_enabled"],
        "metrics": {key: report["metrics"].get(key) for key in (
            "answer_accuracy", "groundedness", "forbidden_claim_rate", "average_latency_ms",
            "p50_latency_ms", "p95_latency_ms")},
        "cases": [{"case_id": item["case_id"], "status": item["status"],
                   "generation": item["generation"], "failure_reasons": item["failure_reasons"]}
                  for item in report["cases"]],
    }, indent=2, default=str) + "\n", encoding="utf-8")
    end_to_end = (f"{report['end_to_end_pass_rate']:.1%}"
                  if report["end_to_end_pass_rate"] is not None else "not evaluated")
    (output_dir / "evaluation_summary.md").write_text(
        "# ICIA evaluation summary\n\n"
        f"- End-to-end pass rate: {end_to_end}\n"
        f"- Retrieval Recall@1/3/5/10: {report['metrics']['recall_at_1']:.3f} / "
        f"{report['metrics']['recall_at_3']:.3f} / {report['metrics']['recall_at_5']:.3f} / "
        f"{report['metrics']['recall_at_10']:.3f}\n"
        f"- MRR: {report['metrics']['mrr']:.3f}\n"
        f"- Groundedness: {report['metrics']['groundedness']}\n"
        f"- Citation correctness: {report['metrics']['citation_correctness']}\n", encoding="utf-8")
    print("=" * 50, "\nICIA GOLDEN RAG EVALUATION\n", "=" * 50, sep="")
    print(f"Total Cases: {report['total_cases']}  Passed: {report['passed']}  Failed: {report['failed']}  Errors: {report['errors']}  Retrieval-only: {report['retrieval_only']}")
    print(f"RETRIEVAL EVIDENCE PASS RATE: {report['retrieval_pass_rate']:.1%}")
    if report["end_to_end_pass_rate"] is not None:
        print(f"END-TO-END PASS RATE: {report['end_to_end_pass_rate']:.1%}")
    for case in report["cases"]:
        if case["status"] not in {"PASS", "RETRIEVAL_ONLY"}:
            print(f"\nCASE ID: {case['case_id']}\nQUESTION: {case['question']}\nFAILURE STAGE: {'; '.join(case['failure_reasons'])}")
    print(f"\nReports: {json_path.parent}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/evaluation/golden/standard_agreement_v1.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/evaluation/results")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--document-version-id", type=uuid.UUID)
    parser.add_argument("--tenant-id", type=uuid.UUID)
    parser.add_argument("--corpus-version-id", type=uuid.UUID)
    parser.add_argument("--source-document", default="Standard-agreement.pdf")
    args = parser.parse_args()
    report = asyncio.run(run(args), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    write_reports(report, args.output_dir)
    return 0 if report["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

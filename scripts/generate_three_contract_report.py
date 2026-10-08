"""Generate the third-contract benchmark analysis from frozen-run artifacts."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data/evaluation/results/three-contract-baseline.json"
DATASET = ROOT / "data/evaluation/golden/three_contracts_dev_v1.json"
OUT_MD = ROOT / "docs/evaluation/rag_three_contract_benchmark_20260913.md"
OUT_TAX = ROOT / "data/evaluation/results/three_contract_error_taxonomy.json"


def f(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def metric_row(name: str, item: dict[str, object]) -> str:
    return (
        f"| {name} | {item.get('cases', 0)} | {f(item.get('recall_at_1'))} | "
        f"{f(item.get('recall_at_3'))} | {f(item.get('recall_at_5'))} | "
        f"{f(item.get('recall_at_10'))} | {f(item.get('mrr'))} | "
        f"{f(item.get('ndcg_at_5'))} | {f(item.get('candidate_recall_at_40'))} | "
        f"{item.get('mean_latency_ms', 0):.1f} | {item.get('p50_latency_ms', 0):.1f} | "
        f"{item.get('p95_latency_ms', 0):.1f} |"
    )


def primary_failure(case: dict[str, object], hard_negatives: set[str]) -> str:
    if case["category"] == "insufficient_evidence":
        return "insufficient-evidence case"
    score = case["scores"]
    candidate = case["candidate_scores"]
    if candidate["recall_at_40"] < 1:
        return "dense/BM25 candidate failure"
    if case["category"] == "risk_analysis":
        return "query-type difficulty / multi-provision risk"
    if case["case_id"] in hard_negatives:
        return "hard-negative confusion"
    if score["recall_at_10"] < 1:
        return "ranking/fusion failure"
    return "query ambiguity"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    hard_negative_ids = {
        target for case in dataset["cases"] for target in case.get("hard_negative_of", [])
    }
    version_to_name = {
        "d89c42a8-0cf3-489d-89a7-e76b3b12ced1": "Contract #1",
        "27077304-3640-46f0-84e5-7c26de4fc368": "Contract #2",
        "bf3e4f37-f785-4167-a068-79dfad1d6466": "Contract #3 (MeitY)",
    }

    failures: list[dict[str, object]] = []
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for case in report["cases"]["hybrid_reranked"]:
        if case["scores"]["recall_at_10"] >= 1:
            continue
        version = case["document_version_id"]
        failure = primary_failure(case, hard_negative_ids)
        record = {
            "case_id": case["case_id"],
            "document_version_id": version,
            "document": version_to_name.get(version, version),
            "category": case["category"],
            "failure_type": failure,
            "reranked_recall_at_10": case["scores"]["recall_at_10"],
            "candidate_recall_at_40": case["candidate_scores"]["recall_at_40"],
            "question": case["question"],
        }
        failures.append(record)
        counts[version][failure] += 1
    OUT_TAX.write_text(json.dumps({"failed_cases": failures, "counts_by_document": counts}, default=dict, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Three-contract retrieval generalization benchmark — 2026-09-13",
        "",
        "This is a frozen-system evaluation. No embedding, chunking, BM25, RRF, candidate, reranker, prompt, or production-default tuning was performed.",
        "",
        "## Contract #3 provenance and ingestion",
        "",
        "MeitY's official eGov Standards PDF was acquired as `CONTRACT_TEMPLATE / MASTER_SERVICE_AGREEMENT_TEMPLATE`, not as an executed contract. It is pinned to document version `bf3e4f37-f785-4167-a068-79dfad1d6466`, with 50 pages, 232 chunks, and 232 embeddings. The validated dataset contains 38 cases: 34 retrieval cases and 4 insufficient-evidence safety cases.",
        "",
        "See `meity_cloud_msa_acquisition_report.json`, `meity_cloud_msa_ingestion_report.json`, `meity_cloud_msa_golden_validation.json`, and `meity-cloud-msa-baseline/chunking_report.json` for machine-readable provenance and diagnostics.",
        "",
        "## Frozen benchmark metrics",
        "",
        "| Method | n | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 | Mean ms | P50 ms | P95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method, item in report["metrics"].items():
        lines.append(metric_row(method, item))
    lines.extend(["", "## Per-contract results", ""])
    for version, name in version_to_name.items():
        lines.extend([
            f"### {name}", "",
            "| Method | n | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 | Mean ms | P50 ms | P95 ms |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for method, groups in report["by_contract"].items():
            lines.append(metric_row(method, groups[version]))
        lines.append("")

    lines.extend([
        "## Contract #3 category matrix",
        "",
        "Categories with fewer than three cases are directional only and are not used for broad claims.",
        "",
        "| Category | n | Hybrid R@1/R@3/R@5/R@10 | Hybrid MRR | Reranked R@1/R@3/R@5/R@10 | Reranked MRR | Candidate R@40 |",
        "|---|---:|---|---:|---|---:|---:|",
    ])
    prefix = "bf3e4f37-f785-4167-a068-79dfad1d6466:"
    categories = sorted(key.removeprefix(prefix) for key in report["by_category"]["hybrid"] if key.startswith(prefix))
    for category in categories:
        hybrid = report["by_category"]["hybrid"][prefix + category]
        reranked = report["by_category"]["hybrid_reranked"][prefix + category]
        vals = lambda x: "/".join(f(x[k]) for k in ("recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10"))
        lines.append(f"| {category} | {hybrid['cases']} | {vals(hybrid)} | {f(hybrid['mrr'])} | {vals(reranked)} | {f(reranked['mrr'])} | {f(reranked['candidate_recall_at_40'])} |")

    lines.extend([
        "",
        "## Cross-document error taxonomy",
        "",
        "The case-level taxonomy is in `three_contract_error_taxonomy.json`. It classifies every case that missed R@10 after reranking using candidate recall, hard-negative links, and category/query structure. It is an evaluation taxonomy, not a claim that one mechanism is proven causal.",
        "",
        "| Document | Candidate failures | Ranking/fusion | Hard-negative confusion | Risk/query difficulty | Insufficient evidence | Other |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for version, name in version_to_name.items():
        c = counts[version]
        lines.append(f"| {name} | {c['dense/BM25 candidate failure']} | {c['ranking/fusion failure']} | {c['hard-negative confusion']} | {c['query-type difficulty / multi-provision risk']} | {c['insufficient-evidence case']} | {c['query ambiguity']} |")

    lines.extend([
        "",
        "## Generalization analysis",
        "",
        "1. Dense retrieval generalizes partially: Contract #3 is stronger than Contract #2 at R@1/R@3/R@10 and has Candidate R@40 0.912, but it remains below Contract #1 at R@1 and R@3.",
        "2. BM25 also generalizes partially: MeitY reaches R@1 0.480 and R@10 0.775, above Contract #2 but below Contract #1 at R@10; exact terminology helps this document.",
        "3. Hybrid does not consistently improve every document: it improves Contract #3 over dense at R@1/R@3 and Candidate R@40, but is below dense for Contract #1 R@3/R@5 and Contract #2 at R@3/R@5.",
        "4. Reranking consistently improves early ranking in aggregate and improves Contract #3 R@5/R@10/MRR/nDCG, but not Contract #3 R@1; it also lowers Contract #1 R@10. The gain is not uniform.",
        "5. Repeating failures are early-rank confusion with evidence still in the candidate pool, plus multi-provision risk questions. These are visible across the contracts, though magnitude varies.",
        "6. Document-specific behavior is strongest in MeitY's exact clause terminology and high heading/clause cohesion (0.698), while Contract #2 has many short chunks and lower cohesion; this is correlation, not a causal result.",
        "7. Long-document fragmentation is not supported as a universal explanation: MeitY has 232 chunks, median 109 tokens, and high evidence containment (0.953), yet still has hard early-rank misses; Contract #2's 669 chunks and median 20 tokens remain a stronger structure-specific concern.",
        "8. The measured pattern is primarily ranking/query-type difficulty for MeitY risk cases, with some candidate weakness in indemnity/liability and termination. It is not a consistently weak Candidate R@40 result.",
        "",
        "## Next decision gate",
        "",
        "Decision C is the best-supported next experiment: run a controlled reranker comparison because Candidate R@40 remains strong (0.879 combined; 0.941 for MeitY hybrid) while early-rank confusion remains. Keep the current reranker and all frozen retrieval defaults unchanged during that experiment. A separate chunking experiment is not yet justified as the immediate next step, although Contract #2 structure should remain a preregistered covariate.",
        "",
        "Insufficient-evidence cases were excluded from retrieval recall by design and remain safety-answer cases. No production-default changes were made.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

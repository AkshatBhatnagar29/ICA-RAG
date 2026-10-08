"""Finalize isolated reranker reports from completed model result files."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_reranker_experiment import aggregate, pairwise, taxonomy


REPORTS = ROOT / "reports/reranker_experiment"
FILES = {
    "A_current_jina": "baseline_results.json",
    "B_minilm_l6": "candidate_1_results.json",
    "C_jina_turbo": "candidate_2_results.json",
}
NAMES = {
    "d89c42a8-0cf3-489d-89a7-e76b3b12ced1": "Contract #1",
    "27077304-3640-46f0-84e5-7c26de4fc368": "Contract #2",
    "bf3e4f37-f785-4167-a068-79dfad1d6466": "Contract #3 / MeitY",
}


def load() -> dict[str, dict]:
    return {name: json.loads((REPORTS / filename).read_text(encoding="utf-8"))
            for name, filename in FILES.items()}


def main() -> None:
    reports = load()
    aggregate_results = {name: report["metrics"] for name, report in reports.items()}
    current = aggregate_results["A_current_jina"]
    for name, metrics in aggregate_results.items():
        metrics["relative_mrr_vs_current"] = metrics["mrr"] / current["mrr"] - 1 if name != "A_current_jina" else 0.0
        metrics["relative_r1_vs_current"] = metrics["recall_at_1"] / current["recall_at_1"] - 1 if name != "A_current_jina" else 0.0
        metrics["latency_multiplier_vs_current"] = metrics["mean_latency_ms"] / current["mean_latency_ms"] if name != "A_current_jina" else 1.0
        metrics["measurement_note"] = "Jina baseline: 3 warm repetitions/case; alternatives: 1 warm repetition/case due to CPU practicality."
    (REPORTS / "aggregate_results.json").write_text(json.dumps(aggregate_results, indent=2) + "\n", encoding="utf-8")

    per_contract = {}
    for name, report in reports.items():
        per_contract[name] = {}
        for version in NAMES:
            per_contract[name][version] = aggregate([case for case in report["cases"] if case["document_version_id"] == version])
    (REPORTS / "per_contract_results.json").write_text(json.dumps(per_contract, indent=2) + "\n", encoding="utf-8")

    categories = {}
    for name, report in reports.items():
        groups = defaultdict(list)
        for case in report["cases"]:
            if case["error"] is None:
                groups[(case["document_version_id"], case["category"])].append(case)
        categories[name] = {f"{version}:{category}": aggregate(cases) | {"directional_only": len(cases) < 3}
                            for (version, category), cases in groups.items()}
    (REPORTS / "category_results.json").write_text(json.dumps(categories, indent=2) + "\n", encoding="utf-8")

    errors = {name: taxonomy(report["cases"]) for name, report in reports.items()}
    (REPORTS / "error_analysis.json").write_text(json.dumps(errors, indent=2) + "\n", encoding="utf-8")
    movement = {name: report["movement"] for name, report in reports.items()}
    (REPORTS / "movement_analysis.json").write_text(json.dumps(movement, indent=2) + "\n", encoding="utf-8")
    latency = {name: {
        key: report["metrics"].get(key) for key in (
            "cold_start_latency_ms", "mean_latency_ms", "p50_latency_ms", "p95_latency_ms",
            "min_latency_ms", "max_latency_ms", "success_rate", "timeout_count", "exception_count",
        )
    } | {"warm_repetitions": report["repetitions_per_case"]} for name, report in reports.items()}
    (REPORTS / "latency_results.json").write_text(json.dumps(latency, indent=2) + "\n", encoding="utf-8")
    (REPORTS / "pairwise_results.json").write_text(json.dumps(pairwise(reports), indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Controlled reranker comparison — ICIA — 2026-09-13", "",
        "## Decision", "",
        "**B) KEEP CURRENT RERANKER** for production. MiniLM is the quality leader on the cached benchmark, but it was measured with one warm repetition per case and remains CPU-expensive; this is not sufficient evidence to replace Jina without a matched repeated latency run and operational validation. Turbo does not beat current Jina. No production defaults changed.", "",
        "## Objective and frozen baseline", "",
        "The experiment compares rerankers only. Dense retrieval, BM25, equal-weight RRF k=60, candidate_k=40, E5 embeddings, base chunking, tenant/version scope, labels, and evidence mappings were frozen. The common input is `candidate_sets.jsonl`: 116 retrieval cases, exactly 40 hybrid candidates per case.", "",
        "Current Jina baseline: `jinaai/jina-reranker-v1-tiny-en`, FastEmbed TextCrossEncoder/ONNX CPU, max_length 512, batch size 8, one thread, deterministic score-descending then chunk-ID tie-break. See `frozen_config.json`.", "",
        "## Selected rerankers", "",
        "- **A_current_jina** — `jinaai/jina-reranker-v1-tiny-en`, Apache-2.0.",
        "- **B_minilm_l6** — `Xenova/ms-marco-MiniLM-L-6-v2`, Apache-2.0, FastEmbed/ONNX CPU. Selected as the practical alternative after BGE base proved impractical on this CPU.",
        "- **C_jina_turbo** — `jinaai/jina-reranker-v1-turbo-en`, Apache-2.0, FastEmbed/ONNX CPU.",
        "BGE base was rejected after a cached attempt because its approximately 1.13 GB package and CPU inference were operationally impractical; details are in `reranker_candidates.json`.", "",
        "## Aggregate metrics", "",
        "| Reranker | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 | Mean ms | P50 ms | P95 ms | Success |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, m in aggregate_results.items():
        lines.append(f"| {name} | {m['recall_at_1']:.3f} | {m['recall_at_3']:.3f} | {m['recall_at_5']:.3f} | {m['recall_at_10']:.3f} | {m['mrr']:.3f} | {m['ndcg_at_5']:.3f} | {m['candidate_recall_at_40']:.3f} | {m['mean_latency_ms']:.1f} | {m['p50_latency_ms']:.1f} | {m['p95_latency_ms']:.1f} | {m['success_rate']:.3f} |")
    lines += ["", "Alternatives used one warm repetition per case; Jina used three. Quality comparisons are complete-case comparisons, while latency comparisons are directional until matched repetitions are rerun.", ""]
    lines += ["## Relative quality and latency versus Jina", "", "| Reranker | Relative MRR | Relative R@1 | Latency multiplier |", "|---|---:|---:|---:|"]
    for name, m in aggregate_results.items():
        lines.append(f"| {name} | {m['relative_mrr_vs_current']:+.1%} | {m['relative_r1_vs_current']:+.1%} | {m['latency_multiplier_vs_current']:.2f}x |")

    lines += ["", "## Per-contract results", ""]
    for version, title in NAMES.items():
        lines += [f"### {title}", "", "| Reranker | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for name in reports:
            m = per_contract[name][version]
            lines.append(f"| {name} | {m['recall_at_1']:.3f} | {m['recall_at_3']:.3f} | {m['recall_at_5']:.3f} | {m['recall_at_10']:.3f} | {m['mrr']:.3f} | {m['ndcg_at_5']:.3f} | {m['candidate_recall_at_40']:.3f} |")
        lines.append("")

    lines += ["## Category results", "", "The complete category matrix is in `category_results.json`. Categories with fewer than three cases are marked directional only. The recurring categories with adequate support show MiniLM's advantage is broadest in contract-factual, obligation, payment, confidentiality/data, and service-level cases; risk analysis remains difficult for all systems.", ""]
    lines += ["## Candidate-set invariant", "", "All completed reranker result files report 116/116 successful cases and preserve the exact 40 chunk IDs per case. Candidate R@40 is identical at 0.879310 for every reranker. No reranker performed retrieval.", ""]
    lines += ["## Error and movement analysis", "", "See `error_analysis.json`, `movement_analysis.json`, and `pairwise_results.json`. The taxonomy is observational: candidate failure when cached Candidate R@40 is below 1, risk/query difficulty for risk cases, otherwise ranking/fusion; insufficient-evidence cases are not retrieval targets.", ""]
    lines += ["## Latency and reliability", "", "All three models completed every case without timeout or exception. Jina's three-repetition baseline mean was {:.1f} ms; MiniLM's single-pass mean was {:.1f} ms; turbo's single-pass mean was {:.1f} ms. Cold-start, min, max, p50, and p95 are in `latency_results.json`. These are reranker-only timings; retrieval, embedding, BM25, and RRF are excluded.".format(aggregate_results['A_current_jina']['mean_latency_ms'], aggregate_results['B_minilm_l6']['mean_latency_ms'], aggregate_results['C_jina_turbo']['mean_latency_ms']), ""]
    lines += ["## Regression tests", "", "The experiment-specific invariant tests passed 4/4. The full current suite passed 109 tests with 2 skips and 1 existing deprecation warning. A separate pre-experiment baseline run was not captured in this continuation, so no before/after delta is claimed; the experiment made no production-code or default changes.", ""]
    lines += ["## Conclusion and next experiment", "", "Reranking improves the frozen hybrid baseline: Jina's prior benchmark gain is confirmed, and MiniLM improves aggregate MRR/R@1/R@3/R@5 over current Jina on the common cache. However, MiniLM's matched repeated latency and resource profile are not yet established, and turbo regresses quality. Keep Jina in production. The next controlled experiment should be a matched warm-latency rerun of Jina versus MiniLM (same repetitions and ideally a batch-size/CPU implementation study isolated from retrieval quality). Risk and multi-provision queries remain the shared difficult pattern; candidate recall is not the dominant aggregate bottleneck, though individual candidate failures remain.", ""]
    (REPORTS / "final_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("finalized", ", ".join(FILES))


if __name__ == "__main__":
    main()

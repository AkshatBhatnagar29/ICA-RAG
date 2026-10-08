"""Evaluate three local rerankers against one immutable candidate cache."""

# The repository-root path bootstrap must precede application imports.
# ruff: noqa: I001

from __future__ import annotations

import argparse
import asyncio
import json
import math
import selectors
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.evaluation.golden_metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from app.services.evaluation.metrics import percentile


MODELS = {
    "A_current_jina": "jinaai/jina-reranker-v1-tiny-en",
    "B_minilm_l6": "Xenova/ms-marco-MiniLM-L-6-v2",
    "C_jina_turbo": "jinaai/jina-reranker-v1-turbo-en",
}


def norm(value: str) -> str:
    return " ".join(value.casefold().split())


def expected_match(row: dict[str, Any], evidence: dict[str, Any]) -> bool:
    if evidence.get("chunk_id") and str(evidence["chunk_id"]) == str(row["chunk_id"]):
        return True
    anchor = evidence.get("anchor")
    if not anchor:
        return False
    actual = norm(row.get("text", ""))
    expected = norm(anchor)
    if expected in actual and evidence.get("page") in (None, row.get("page_start"), row.get("page_end")):
        return True
    terms = [term for term in expected.split() if term.isalnum() and len(term) > 3]
    if not terms:
        return False
    return sum(term in actual for term in terms) / len(terms) >= 0.6


def score(rows: list[dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    expected = case.get("expected_evidence", [])
    relevant = []
    for row in rows:
        if any(expected_match(row, evidence) for evidence in expected):
            relevant.append(row)
    return {
        "recall_at_1": recall_at_k(rows, expected, 1),
        "recall_at_3": recall_at_k(rows, expected, 3),
        "recall_at_5": recall_at_k(rows, expected, 5),
        "recall_at_10": recall_at_k(rows, expected, 10),
        "mrr": reciprocal_rank(rows, expected),
        "ndcg_at_5": ndcg_at_k(rows, expected, 5),
        "expected_found": bool(relevant),
        "gold_ranks": [row["rank"] for row in relevant],
    }


def aggregate(samples: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [item for item in samples if item["error"] is None]
    if not successful:
        return {"cases": len(samples), "successful_cases": 0, "success_rate": 0.0}
    values = [item["latency_ms"] for item in successful]
    return {
        "cases": len(samples),
        "successful_cases": len(successful),
        "success_rate": len(successful) / len(samples),
        "timeout_count": sum(item["error_type"] == "timeout" for item in samples),
        "exception_count": sum(item["error"] is not None and item["error_type"] != "timeout" for item in samples),
        "recall_at_1": statistics.mean(item["scores"]["recall_at_1"] for item in successful),
        "recall_at_3": statistics.mean(item["scores"]["recall_at_3"] for item in successful),
        "recall_at_5": statistics.mean(item["scores"]["recall_at_5"] for item in successful),
        "recall_at_10": statistics.mean(item["scores"]["recall_at_10"] for item in successful),
        "mrr": statistics.mean(item["scores"]["mrr"] for item in successful),
        "ndcg_at_5": statistics.mean(item["scores"]["ndcg_at_5"] for item in successful),
        "candidate_recall_at_40": statistics.mean(item["candidate_recall_at_40"] for item in successful),
        "mean_latency_ms": statistics.mean(values),
        "p50_latency_ms": percentile(values, 50),
        "p95_latency_ms": percentile(values, 95),
        "p99_latency_ms": percentile(values, 99),
        "min_latency_ms": min(values),
        "max_latency_ms": max(values),
    }


def rows_for_reranked(candidates: list[dict[str, Any]], scores: list[float]) -> list[dict[str, Any]]:
    ranked = sorted(
        zip(candidates, scores, strict=True),
        key=lambda pair: (-float(pair[1]), str(pair[0]["chunk_id"])),
    )
    result = []
    for rank, (candidate, value) in enumerate(ranked, 1):
        item = dict(candidate)
        item["rank"] = rank
        item["reranker_score"] = float(value)
        item["original_rank"] = candidate["rank"]
        result.append(item)
    return result


def movement(samples: list[dict[str, Any]]) -> dict[str, Any]:
    movements: list[int] = []
    gold_movements: list[int] = []
    upward = downward = unchanged = 0
    for sample in samples:
        before = {row["chunk_id"]: row["rank"] for row in sample["candidates"]}
        after = {row["chunk_id"]: row["rank"] for row in sample["results"]}
        for chunk_id, old_rank in before.items():
            delta = old_rank - after[chunk_id]
            movements.append(delta)
            upward += delta > 0
            downward += delta < 0
            unchanged += delta == 0
        for row in sample["candidates"]:
            if any(expected_match(row, evidence) for evidence in sample["expected_evidence"]):
                gold_movements.append(before[row["chunk_id"]] - after[row["chunk_id"]])
    return {
        "chunks_observed": len(movements),
        "moved_upward": upward,
        "moved_downward": downward,
        "unchanged": unchanged,
        "mean_rank_movement": statistics.mean(movements) if movements else 0.0,
        "median_rank_movement": statistics.median(movements) if movements else 0.0,
        "gold_chunks_observed": len(gold_movements),
        "gold_mean_rank_movement": statistics.mean(gold_movements) if gold_movements else 0.0,
        "gold_median_rank_movement": statistics.median(gold_movements) if gold_movements else 0.0,
    }


def taxonomy(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for sample in samples:
        if sample["scores"]["recall_at_10"] >= 1:
            continue
        if sample["category"] == "insufficient_evidence":
            failure = "insufficient evidence"
        elif sample["candidate_recall_at_40"] < 1:
            failure = "candidate failure"
        elif sample["category"] == "risk_analysis":
            failure = "risk/query difficulty"
        else:
            failure = "ranking/fusion"
        output.append({"case_id": sample["case_id"], "document_version_id": sample["document_version_id"],
                       "category": sample["category"], "failure_type": failure,
                       "reranked_recall_at_10": sample["scores"]["recall_at_10"],
                       "candidate_recall_at_40": sample["candidate_recall_at_40"],
                       "question": sample["question"]})
    return output


async def rerank_model(model_id: str, cases: list[dict[str, Any]], cache_dir: str,
                       batch_size: int, max_length: int, threads: int,
                       repetitions: int, warmups: int) -> dict[str, Any]:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    load_started = time.perf_counter()
    encoder = TextCrossEncoder(model_name=model_id, cache_dir=cache_dir, threads=threads,
                               cuda=False, lazy_load=False)
    load_ms = (time.perf_counter() - load_started) * 1000
    try:
        import psutil
        process = psutil.Process()
        process.cpu_percent(None)
        rss_peak = process.memory_info().rss
        cpu_started = process.cpu_times()
    except ImportError:
        process = None
        rss_peak = None
        cpu_started = None
    warmup_case = cases[0]
    for _ in range(warmups):
        list(encoder.rerank(warmup_case["query"], [row["text"] for row in warmup_case["candidates"]],
                            batch_size=batch_size, max_length=max_length))
        if process is not None:
            rss_peak = max(rss_peak or 0, process.memory_info().rss)
    samples: list[dict[str, Any]] = []
    for case in cases:
        candidates = case["candidates"]
        latencies: list[float] = []
        error = None
        error_type = None
        results: list[dict[str, Any]] = []
        scores: list[float] = []
        for _ in range(repetitions):
            started = time.perf_counter()
            try:
                raw_scores = list(encoder.rerank(case["query"], [row["text"] for row in candidates],
                                                 batch_size=batch_size, max_length=max_length))
                elapsed = (time.perf_counter() - started) * 1000
                if len(raw_scores) != len(candidates) or not all(math.isfinite(float(value)) for value in raw_scores):
                    raise ValueError("invalid score count or non-finite score")
                latencies.append(elapsed)
                if process is not None:
                    rss_peak = max(rss_peak or 0, process.memory_info().rss)
                if not scores:
                    scores = [float(value) for value in raw_scores]
                    results = rows_for_reranked(candidates, scores)
            except TimeoutError as exc:
                error = str(exc)
                error_type = "timeout"
                break
            except Exception as exc:  # noqa: BLE001 - isolate model/case failures in evaluation
                error = f"{type(exc).__name__}: {exc}"
                error_type = "exception"
                break
        if error is None:
            result_score = score(results, case)
            candidate_recall = case["candidate_recall_at_40"]
            invariant = {row["chunk_id"] for row in candidates} == {row["chunk_id"] for row in results}
        else:
            result_score = {key: 0.0 for key in ("recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10", "mrr", "ndcg_at_5")}
            result_score |= {"expected_found": False, "gold_ranks": []}
            candidate_recall = case["candidate_recall_at_40"]
            invariant = False
        samples.append({
            "case_id": case["case_id"], "document_version_id": case["document_version_id"],
            "category": case["category"], "question": case["query"],
            "expected_evidence": case["expected_evidence"], "candidates": candidates,
            "results": results, "scores": result_score, "candidate_recall_at_40": candidate_recall,
            "candidate_set_invariant": invariant, "latency_ms": statistics.mean(latencies) if latencies else 0.0,
            "warm_latencies_ms": latencies, "warm_repetitions": len(latencies),
            "error": error, "error_type": error_type,
        })
    metrics = aggregate(samples)
    metrics["cold_start_latency_ms"] = load_ms
    metrics["warmup_runs"] = warmups
    metrics["measured_repetitions_per_case"] = repetitions
    metrics["timing_boundary"] = "TextCrossEncoder.rerank only; model load excluded"
    metrics["peak_rss_mb"] = round(rss_peak / (1024 * 1024), 2) if rss_peak else None
    if process is not None and cpu_started is not None:
        cpu_end = process.cpu_times()
        cpu_seconds = (cpu_end.user + cpu_end.system) - (cpu_started.user + cpu_started.system)
        measured_calls = len(cases) * repetitions
        metrics["cpu_time_seconds"] = round(cpu_seconds, 3)
        metrics["cpu_utilization_percent_of_wall"] = round(
            cpu_seconds / max(sum(item["latency_ms"] for item in samples) / 1000, 0.001) * 100, 2
        )
        metrics["throughput_queries_per_sec"] = round(measured_calls / max(sum(item["latency_ms"] for item in samples) / 1000, 0.001), 4)
    else:
        metrics["cpu_time_seconds"] = None
        metrics["cpu_utilization_percent_of_wall"] = None
        metrics["throughput_queries_per_sec"] = None
    return {"model_id": model_id, "timestamp": datetime.now(UTC).isoformat(),
            "repetitions_per_case": repetitions, "metrics": metrics, "cases": samples,
            "movement": movement(samples), "errors": taxonomy(samples)}


def category_results(report: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in report["cases"]:
        if case["error"] is None:
            groups[case["category"]].append(case)
    return {category: aggregate(values) | {"directional_only": len(values) < 3}
            for category, values in groups.items()}


def pairwise(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = {case["case_id"]: case for case in reports["A_current_jina"]["cases"]}
    result: dict[str, Any] = {}
    for name, report in reports.items():
        if name == "A_current_jina":
            continue
        candidate = {case["case_id"]: case for case in report["cases"]}
        current_wins = candidate_wins = both_fail = 0
        gold_rank_before: list[int] = []
        gold_rank_after: list[int] = []
        for case_id, current in baseline.items():
            other = candidate[case_id]
            if current["scores"]["recall_at_10"] >= 1 and other["scores"]["recall_at_10"] < 1:
                current_wins += 1
            if other["scores"]["recall_at_10"] >= 1 and current["scores"]["recall_at_10"] < 1:
                candidate_wins += 1
            if current["scores"]["recall_at_10"] < 1 and other["scores"]["recall_at_10"] < 1:
                both_fail += 1
            gold_rank_before.extend(row["rank"] for row in current["candidates"] if any(expected_match(row, e) for e in current["expected_evidence"]))
            gold_rank_after.extend(row["rank"] for row in other["results"] if any(expected_match(row, e) for e in other["expected_evidence"]))
        result[name] = {"current_succeeds_candidate_fails": current_wins,
                        "candidate_succeeds_current_fails": candidate_wins,
                        "both_fail_r10": both_fail,
                        "gold_rank_before_mean": statistics.mean(gold_rank_before) if gold_rank_before else None,
                        "gold_rank_after_mean": statistics.mean(gold_rank_after) if gold_rank_after else None}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sets", type=Path, default=ROOT / "reports/reranker_experiment/candidate_sets.jsonl")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/reranker_experiment")
    parser.add_argument("--cache-dir", default="data/model-cache/reranker")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--model", choices=tuple(MODELS), help="Run only one model; useful for isolated resource-limited passes.")
    args = parser.parse_args()
    cases = [json.loads(line) for line in args.candidate_sets.read_text(encoding="utf-8").splitlines() if line.strip()]
    reports: dict[str, dict[str, Any]] = {}
    selected_models = {args.model: MODELS[args.model]} if args.model else MODELS
    for name, model_id in selected_models.items():
        report = asyncio.run(rerank_model(model_id, cases, args.cache_dir, args.batch_size,
                                          args.max_length, args.threads, args.repetitions, args.warmups),
                             loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
        reports[name] = report
        target = args.output_dir / ({"A_current_jina": "baseline_results.json", "B_minilm_l6": "candidate_1_results.json", "C_jina_turbo": "candidate_2_results.json"}[name])
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.model:
        print(json.dumps({args.model: reports[args.model]["metrics"]}, indent=2))
        return 0

    aggregate_report = {name: report["metrics"] for name, report in reports.items()}
    current = aggregate_report["A_current_jina"]
    for name, metrics in aggregate_report.items():
        metrics["relative_mrr_vs_current"] = (metrics["mrr"] / current["mrr"] - 1) if name != "A_current_jina" else 0.0
        metrics["relative_r1_vs_current"] = (metrics["recall_at_1"] / current["recall_at_1"] - 1) if name != "A_current_jina" else 0.0
        metrics["latency_multiplier_vs_current"] = (metrics["mean_latency_ms"] / current["mean_latency_ms"]) if name != "A_current_jina" else 1.0
    (args.output_dir / "aggregate_results.json").write_text(json.dumps(aggregate_report, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "per_contract_results.json").write_text(json.dumps({
        name: {
            version: aggregate([case for case in report["cases"] if case["document_version_id"] == version])
            for version in sorted({case["document_version_id"] for case in report["cases"]})
        } for name, report in reports.items()
    }, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "category_results.json").write_text(json.dumps({name: category_results(report) for name, report in reports.items()}, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "movement_analysis.json").write_text(json.dumps({name: {"movement": report["movement"], "errors": report["errors"]} for name, report in reports.items()}, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "error_analysis.json").write_text(json.dumps({name: report["errors"] for name, report in reports.items()}, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "latency_results.json").write_text(json.dumps({name: {
        "cold_start_latency_ms": report["metrics"].get("cold_start_latency_ms"),
        "mean_latency_ms": report["metrics"].get("mean_latency_ms"),
        "p50_latency_ms": report["metrics"].get("p50_latency_ms"),
        "p95_latency_ms": report["metrics"].get("p95_latency_ms"),
        "p99_latency_ms": report["metrics"].get("p99_latency_ms"),
        "min_latency_ms": report["metrics"].get("min_latency_ms"),
        "max_latency_ms": report["metrics"].get("max_latency_ms"),
        "warm_repetitions": report["repetitions_per_case"],
        "warmup_runs": report["metrics"].get("warmup_runs"),
        "peak_rss_mb": report["metrics"].get("peak_rss_mb"),
        "cpu_time_seconds": report["metrics"].get("cpu_time_seconds"),
        "cpu_utilization_percent_of_wall": report["metrics"].get("cpu_utilization_percent_of_wall"),
        "throughput_queries_per_sec": report["metrics"].get("throughput_queries_per_sec"),
    } for name, report in reports.items()}, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "pairwise_results.json").write_text(json.dumps(pairwise(reports), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(aggregate_report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

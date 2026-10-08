"""Snapshot the frozen baseline and materialize shared hybrid candidates."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings


REPORTS = ROOT / "reports/reranker_experiment"
BASELINE = ROOT / "data/evaluation/results/three-contract-baseline.json"
DATASET = ROOT / "data/evaluation/golden/three_contracts_dev_v1.json"


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> None:
    settings = get_settings()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in dataset["cases"]}
    REPORTS.mkdir(parents=True, exist_ok=True)

    frozen = {
        "snapshot_timestamp": datetime.now(UTC).isoformat(),
        "git_commit_sha": git_sha(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "packages": {name: package_version(name) for name in (
                "fastembed", "onnxruntime", "numpy", "sqlalchemy", "pydantic"
            )},
        },
        "dataset": {
            "path": str(DATASET.relative_to(ROOT)),
            "name": dataset["dataset_name"],
            "version": dataset["version"],
            "case_count": len(dataset["cases"]),
            "retrieval_case_count": sum(case.get("retrieval_applicable", True) for case in dataset["cases"]),
            "source_documents": dataset["source_documents"],
        },
        "retrieval": {
            "embedding_model": settings.embedding_model,
            "embedding_dimension": settings.embedding_dimension,
            "embedding_provider": "LocalE5EmbeddingProvider",
            "chunk_refinement_mode": settings.chunk_refinement_mode,
            "bm25": "materialized authorized chunk set per request",
            "dense_implementation": "RetrievalService dense vector search",
            "rrf_implementation": "equal-weight reciprocal rank fusion",
            "rrf_k": settings.retrieval_rrf_k,
            "dense_weight": 1.0,
            "sparse_weight": 1.0,
            "candidate_k": settings.reranker_candidate_k,
            "tenant_and_version_scope": True,
            "deterministic_tie_breaking": True,
        },
        "baseline_reranker": {
            "name": "A_current_jina",
            "model": settings.reranker_model,
            "model_version": settings.reranker_model_version,
            "backend": "FastEmbed TextCrossEncoder / ONNX Runtime CPU",
            "cache_path": settings.reranker_cache_path,
            "max_length": settings.reranker_max_length,
            "batch_size": settings.reranker_batch_size,
            "threads": settings.reranker_threads,
            "candidate_k": settings.reranker_candidate_k,
            "preprocessing": "query plus candidate text passed to FastEmbed TextCrossEncoder",
            "scoring": "raw cross-encoder score, descending",
            "tie_breaking": "score descending then chunk UUID ascending",
        },
        "production_defaults_changed": False,
    }
    (REPORTS / "frozen_config.json").write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")

    candidates_path = REPORTS / "candidate_sets.jsonl"
    with candidates_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in baseline["cases"]["hybrid_reranked"]:
            case = cases[item["case_id"]]
            if not case.get("retrieval_applicable", True):
                continue
            rows = item["candidate_results"][: settings.reranker_candidate_k]
            if len(rows) != settings.reranker_candidate_k:
                raise RuntimeError(f"{item['case_id']} has {len(rows)} candidates, expected 40")
            record = {
                "case_id": item["case_id"],
                "document_version_id": item["document_version_id"],
                "query": item["question"],
                "category": case.get("category"),
                "expected_evidence": case.get("expected_evidence", []),
                "expected_evidence_ids": [
                    evidence.get("chunk_id") or evidence.get("anchor")
                    for evidence in case.get("expected_evidence", [])
                ],
                "candidate_k": settings.reranker_candidate_k,
                "candidates": rows,
                "candidate_recall_at_40": item["candidate_scores"]["recall_at_40"],
                "source": "three-contract-baseline.json hybrid_reranked candidate_results",
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    candidates = sum(1 for _ in candidates_path.open(encoding="utf-8"))
    (REPORTS / "reranker_candidates.json").write_text(json.dumps({
        "selection_policy": "Exactly two locally compatible alternatives available in installed FastEmbed.",
        "candidates": [
            {
                "name": "B_minilm_l6",
                "model_id": "Xenova/ms-marco-MiniLM-L-6-v2",
                "license": "Apache-2.0",
                "backend": "FastEmbed TextCrossEncoder / ONNX Runtime CPU",
                "expected_input": "query plus candidate passage",
                "maximum_sequence_length": "FastEmbed wrapper max_length=512 for this experiment",
                "language": "English-focused",
                "memory": "FastEmbed registry size approximately 0.08 GB; CPU model memory not measured before download",
                "reason": "Small locally supported Apache-2.0 cross-encoder alternative that is practical on the development CPU and provides an independent architecture comparison.",
            },
            {
                "name": "C_jina_turbo",
                "model_id": "jinaai/jina-reranker-v1-turbo-en",
                "license": "Apache-2.0",
                "backend": "FastEmbed TextCrossEncoder / ONNX Runtime CPU",
                "expected_input": "query plus candidate passage",
                "maximum_sequence_length": "FastEmbed wrapper max_length=512 for this experiment",
                "language": "English",
                "memory": "FastEmbed registry size approximately 0.15 GB; CPU model memory not measured before download",
                "reason": "Same vendor family but larger turbo model, isolating a capacity/latency tradeoff while retaining Apache-2.0 licensing and local execution.",
            },
        ],
        "not_selected": {
            "BAAI/bge-reranker-base": "Rejected after an isolated cached single-pass attempt: approximately 1.13 GB package and impractical CPU inference time on this development machine.",
            "jinaai/jina-reranker-v2-base-multilingual": "Not selected because its CC-BY-NC-4.0 license is less suitable for a general project default and it is materially larger.",
        },
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_cases": candidates, "candidate_path": str(candidates_path)}, indent=2))


if __name__ == "__main__":
    main()

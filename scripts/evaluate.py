"""Run independent Phase 13 evaluation benchmarks and emit machine-readable JSON."""
from __future__ import annotations

import argparse
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.evaluation.datasets import load_dataset
from app.services.evaluation.runner import evaluate_retrieval, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="retrieval_v1")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    path = ROOT / "data" / "evaluation" / "retrieval" / f"{args.dataset}.json"
    result = evaluate_retrieval(load_dataset(path), args.top_k)
    result["timestamp"] = datetime.now(UTC).isoformat()
    result["environment"] = {"python": platform.python_version(), "platform": platform.platform()}
    output = args.output or ROOT / "data" / "evaluation" / "results" / f"{args.dataset}.json"
    write_json(output, result)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

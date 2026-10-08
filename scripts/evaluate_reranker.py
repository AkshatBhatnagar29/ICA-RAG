"""Compatibility entry point for the production golden reranker benchmark.

The benchmark lives in evaluate_retrieval.py because reranker quality must be
compared with the pre-rerank candidate pool using identical queries.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).with_name("evaluate_retrieval.py")
    sys.argv[0] = str(script)
    runpy.run_path(str(script), run_name="__main__")

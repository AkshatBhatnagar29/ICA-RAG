"""Pin every MeitY golden case to the acquired immutable version."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/evaluation/golden/meity_cloud_msa_v1.json"
VERSION = "bf3e4f37-f785-4167-a068-79dfad1d6466"


payload = json.loads(DATASET.read_text(encoding="utf-8"))
for case in payload["cases"]:
    case["document_version_id"] = VERSION
DATASET.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

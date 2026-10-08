from __future__ import annotations

import json
from pathlib import Path

from app.services.evaluation.models import EvaluationDataset


def load_dataset(path: Path) -> EvaluationDataset:
    """Load a versioned benchmark; raw sources are read-only inputs, never rewritten."""
    return EvaluationDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))


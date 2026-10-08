from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str = Field(min_length=1)
    corpus: str = Field(pattern=r"^(contract|legal)$")
    source_dataset: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    source_row: int | None = Field(default=None, ge=0)
    source_identifier: str = Field(min_length=1)
    query: str = Field(min_length=1)
    text: str = Field(min_length=1)
    expected_ids: list[str] = Field(min_length=1)
    label_quality: str = Field(pattern=r"^(gold|silver|heuristic)$")
    metadata: dict[str, str] = Field(default_factory=dict)


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    records: list[EvaluationRecord] = Field(min_length=1)


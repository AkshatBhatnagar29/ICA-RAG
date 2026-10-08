from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeneratedCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    citation_id: str = Field(min_length=2, max_length=20)


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=20000)
    citations: list[GeneratedCitation] = Field(min_length=1, max_length=50)
    limitations: str | None = Field(default=None, max_length=5000)

    @field_validator("answer")
    @classmethod
    def non_blank_answer(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("answer must not be blank")
        return value

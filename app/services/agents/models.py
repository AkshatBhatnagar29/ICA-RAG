from __future__ import annotations

import enum
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentTask(str, enum.Enum):
    CONTRACT_QA = "CONTRACT_QA"
    CONTRACT_RISK_REVIEW = "CONTRACT_RISK_REVIEW"
    CONTRACT_COMPARISON = "CONTRACT_COMPARISON"
    LEGAL_CONTEXT = "LEGAL_CONTEXT"
    COMBINED_CONTRACT_LEGAL_ANALYSIS = "COMBINED_CONTRACT_LEGAL_ANALYSIS"


class AgentStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_REQUEST = "INVALID_REQUEST"
    TOOL_FAILURE = "TOOL_FAILURE"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"


class ToolStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TIMEOUT = "TIMEOUT"
    TRANSIENT_ERROR = "TRANSIENT_ERROR"
    FAILED = "FAILED"


class AgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None = None


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=4000)
    tenant_id: uuid.UUID | None = None
    document_version_id: uuid.UUID | None = None
    source_version_id: uuid.UUID | None = None
    target_version_id: uuid.UUID | None = None
    corpus_version_id: uuid.UUID | None = None


class AgentStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=500)
    depends_on: list[str] = Field(default_factory=list)


class AgentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: AgentTask
    steps: list[AgentStep] = Field(min_length=1)
    required_evidence: set[str] = Field(default_factory=set)
    stopping_condition: str = Field(min_length=1, max_length=500)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ToolStatus
    data: Any = None
    error_code: str | None = None
    message: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_domain: str | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: uuid.UUID
    status: AgentStatus
    task_type: AgentTask
    answer: str
    findings: list[str] = Field(default_factory=list)
    contract_evidence: list[str] = Field(default_factory=list)
    legal_evidence: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    execution_summary: dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: uuid.UUID
    context: AgentContext
    task: AgentTask
    plan: AgentPlan
    completed_steps: list[str] = Field(default_factory=list)
    tool_results: dict[str, ToolResult] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    contract_evidence: list[str] = Field(default_factory=list)
    legal_evidence: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    status: AgentStatus = AgentStatus.COMPLETED

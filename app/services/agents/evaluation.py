from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.services.agents.models import AgentPlan, AgentResponse, AgentTask


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    request: str
    expected_task: AgentTask
    expected_tools: tuple[str, ...]
    requires_contract: bool
    requires_legal: bool
    expects_insufficient: bool = False


@dataclass(frozen=True)
class EvaluationMetrics:
    total: int
    routing_accuracy: float
    tool_selection_accuracy: float
    plan_validity_rate: float
    execution_success_rate: float
    evidence_sufficiency_correctness: float
    end_to_end_task_success: float
    average_tool_calls: float
    unsupported_tool_rejection_rate: float = 0.0
    citation_correctness: float = 0.0
    unsupported_claim_rate: float = 0.0
    average_execution_latency_ms: float = 0.0


def citation_correctness(cited_ids: Sequence[str], available_ids: Sequence[str]) -> float:
    """Return the proportion of output citations present in this execution."""
    if not cited_ids:
        return 0.0
    available = set(available_ids)
    return sum(identifier in available for identifier in cited_ids) / len(cited_ids)


def unsupported_claim_rate(claims: Sequence[str], supported_claims: Sequence[str]) -> float:
    """Measure claims not marked as supported by the application evaluator."""
    if not claims:
        return 0.0
    return 1.0 - sum(claim in set(supported_claims) for claim in claims) / len(claims)


def unsupported_tool_rejection_rate(rejected: int, attempted_unsupported: int) -> float:
    if attempted_unsupported < 0 or rejected < 0 or rejected > attempted_unsupported:
        raise ValueError("invalid unsupported-tool counts")
    return rejected / attempted_unsupported if attempted_unsupported else 0.0


def average_execution_latency(latencies_ms: Sequence[float]) -> float:
    if any(latency < 0 for latency in latencies_ms):
        raise ValueError("latencies cannot be negative")
    return sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0


def evaluate_cases(cases: Sequence[EvaluationCase], plans: Sequence[AgentPlan],
                   responses: Sequence[AgentResponse]) -> EvaluationMetrics:
    total = len(cases)
    if not total or len(plans) != total or len(responses) != total:
        raise ValueError("evaluation inputs must have equal non-zero lengths")
    routes = sum(plan.task == case.expected_task for case, plan in zip(cases, plans, strict=True))
    tools = sum(tuple(step.tool_name for step in plan.steps) == case.expected_tools
                for case, plan in zip(cases, plans, strict=True))
    valid = sum(bool(plan.steps) and all(step.step_id for step in plan.steps) for plan in plans)
    execution = sum(response.status.value == "COMPLETED" for response in responses)
    sufficiency = sum((response.status.value == "INSUFFICIENT_EVIDENCE") == case.expects_insufficient
                      for case, response in zip(cases, responses, strict=True))
    success = sum(response.task_type == case.expected_task and
                  ((response.status.value == "INSUFFICIENT_EVIDENCE") == case.expects_insufficient)
                  for case, response in zip(cases, responses, strict=True))
    return EvaluationMetrics(total, routes / total, tools / total, valid / total, execution / total,
                             sufficiency / total, success / total,
                             sum(len(response.execution_summary.get("tools", [])) for response in responses) / total)

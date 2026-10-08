from __future__ import annotations

import asyncio

from app.observability.metrics import metrics
from app.services.agents.models import AgentState, AgentStatus, ToolResult, ToolStatus
from app.services.agents.registry import ToolRegistry


class AgentExecutor:
    def __init__(self, registry: ToolRegistry, *, max_steps: int = 5, max_tool_calls: int = 5,
                 timeout_seconds: float = 30.0) -> None:
        self.registry = registry
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.timeout_seconds = timeout_seconds

    async def execute(self, state: AgentState) -> AgentState:
        metrics.increment("agent_runs_total")
        if len(state.plan.steps) > self.max_steps:
            state.status = AgentStatus.FAILED
            state.errors.append("agent step limit exceeded")
            return state
        step_ids = [step.step_id for step in state.plan.steps]
        if len(step_ids) != len(set(step_ids)):
            state.status = AgentStatus.FAILED
            state.errors.append("agent plan contains duplicate step IDs")
            return state
        known = set(step_ids)
        dependencies = {step.step_id: set(step.depends_on) for step in state.plan.steps}
        if any(deps - known for deps in dependencies.values()):
            state.status = AgentStatus.FAILED
            state.errors.append("agent plan contains an unknown dependency")
            return state
        visiting: set[str] = set()
        visited: set[str] = set()

        def has_cycle(step_id: str) -> bool:
            if step_id in visiting:
                return True
            if step_id in visited:
                return False
            visiting.add(step_id)
            if any(has_cycle(dep) for dep in dependencies[step_id]):
                return True
            visiting.remove(step_id)
            visited.add(step_id)
            return False

        if any(has_cycle(step_id) for step_id in step_ids):
            state.status = AgentStatus.FAILED
            state.errors.append("agent plan contains a dependency cycle")
            return state
        seen: set[tuple[str, str]] = set()
        for step in state.plan.steps:
            if len(state.completed_steps) >= self.max_tool_calls:
                state.status = AgentStatus.FAILED
                state.errors.append("agent tool-call limit exceeded")
                return state
            if any(dep not in state.completed_steps for dep in step.depends_on):
                state.status = AgentStatus.FAILED
                state.errors.append(f"unsatisfied dependency for {step.step_id}")
                return state
            try:
                tool = self.registry.get(step.tool_name)
                arguments = tool.input_model.model_validate(step.arguments)
            except (ValueError, TypeError) as exc:
                state.status = AgentStatus.FAILED
                state.errors.append(str(exc))
                return state
            key = (tool.name, arguments.model_dump_json())
            if key in seen:
                state.status = AgentStatus.FAILED
                state.errors.append("repeated agent tool call detected")
                return state
            seen.add(key)
            try:
                result = await asyncio.wait_for(tool.handler(arguments, state.context), self.timeout_seconds)
            except TimeoutError:
                metrics.increment("agent_tool_failures_total", category="timeout")
                result = ToolResult(status=ToolStatus.TIMEOUT, error_code="timeout", message="tool timed out")
            except PermissionError as exc:
                result = ToolResult(status=ToolStatus.UNAUTHORIZED, error_code="unauthorized", message=str(exc))
            except (ValueError, TypeError) as exc:
                metrics.increment("agent_tool_failures_total", category="validation")
                result = ToolResult(status=ToolStatus.VALIDATION_ERROR, error_code="validation_error", message=str(exc))
            except RuntimeError as exc:
                metrics.increment("agent_tool_failures_total", category="tool_failure")
                result = ToolResult(status=ToolStatus.FAILED, error_code="tool_failure", message=str(exc))
            state.tool_results[step.step_id] = result
            if result.evidence_domain == "contract":
                state.contract_evidence.extend(x for x in result.evidence_ids if x not in state.contract_evidence)
            if result.evidence_domain == "legal":
                state.legal_evidence.extend(x for x in result.evidence_ids if x not in state.legal_evidence)
            state.evidence_ids.extend(x for x in result.evidence_ids if x not in state.evidence_ids)
            state.completed_steps.append(step.step_id)
            if result.status != ToolStatus.SUCCESS:
                metrics.increment("agent_tool_failures_total", category=result.status.value.lower())
                state.status = AgentStatus.INSUFFICIENT_EVIDENCE if result.status == ToolStatus.INSUFFICIENT_EVIDENCE else AgentStatus.TOOL_FAILURE
                if result.message:
                    state.errors.append(result.message)
                return state
        state.status = AgentStatus.COMPLETED if state.evidence_ids or not state.plan.required_evidence else AgentStatus.INSUFFICIENT_EVIDENCE
        metrics.increment("agent_tool_calls_total", value=len(state.tool_results))
        return state

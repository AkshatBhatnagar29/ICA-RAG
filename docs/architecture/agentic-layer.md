# Phase 11: bounded agentic layer

Phase 11 adds a backend orchestration seam around the existing contract,
retrieval, comparison, generation, and legal-RAG services. It does not replace
those services and it does not create a general autonomous agent.

## Flow

`AgentRequest` is routed deterministically to one of five task types. A typed
planner creates a short `AgentPlan`; the executor validates dependencies and
executes only tools present in the `ToolRegistry`. Every tool receives a
trusted `AgentContext`, including tenant identity, rather than tenant identity
from model-generated arguments.

The current registered tools are `contract_search`, `contract_analysis`,
`contract_comparison`, and `legal_search`. They delegate to existing services;
the agent has no SQLAlchemy repository, filesystem, Redis, shell, or arbitrary
code access. The API is `POST /api/v1/agent/query`.

## Safety and state

Plans and tool arguments are Pydantic-validated. The executor enforces maximum
steps and tool calls, per-tool timeouts, dependency ordering, cycle detection,
and repeated-call detection. Failures are structured and authorization errors
are not retried. Contract and legal evidence IDs are tracked in separate
namespaces (`E...` and `L...` in their originating services). Retrieved text is
passed as data and cannot select tools or alter the plan.

`AgentState` contains operational request, plan, step, result, evidence, error,
and status data only. Hidden chain-of-thought is neither requested nor stored.
No agent persistence or telemetry platform is introduced in this phase.

## Synthesis and citations

When a provider is configured, successful execution builds one bounded context
with clearly labelled contract and legal evidence blocks and sends it to the
existing `LLMProvider`. The response is validated with a strict Pydantic model.
Contract citations are checked by the Phase 7 `verify_citations` implementation;
legal citations are checked by the Phase 10 `verify_legal_citations` implementation.
Unknown, duplicate, cross-namespace, or absent evidence references fail closed.
Provider failures and malformed output produce a structured failure rather than
an apparently successful answer. Without a provider, the endpoint exposes only
the safe execution result and evidence references.

## Boundaries and limitations

The current router and planner are deterministic. Authentication and RBAC remain later-phase work, so
the explicit tenant field is an application boundary, not an identity claim.
This implementation makes no legal conclusion and carries no production SLA
claim. The small regression artifact is behavior-oriented and does not measure
legal correctness or general agent intelligence.

## Why no agent framework

ICIA does not currently use LangChain or LangGraph because its core RAG,
retrieval/ranking, evidence, and tenant boundaries are application-owned and
independently measurable. The current bounded orchestration requirements are
manageable with a small custom layer, and no demonstrated framework
maintenance or scalability requirement exists. Adoption can be reconsidered if
a concrete requirement emerges; this is not a claim that those frameworks are
inherently unsuitable.

## Evaluation seam

The unit tests cover deterministic routing, typed planning, unknown-tool and
cycle rejection, timeout handling, and evidence propagation. Broader routing,
tool-call, citation, and completion metrics belong to Phase 13.

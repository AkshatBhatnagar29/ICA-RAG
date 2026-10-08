# Agent architecture

## Why an agent exists

Normal RAG has one predetermined retrieval path. ICIA's agent selects among
contract search, structured contract analysis, comparison, and versioned legal
search based on the typed request. This is bounded orchestration, not autonomous
code execution.

`router.py:route_task` chooses a task. `planner.py:build_plan` emits typed
`AgentPlan`/`AgentStep` objects with resources and dependencies. `registry.py`
holds named tools, Pydantic input models, handlers, and descriptions.

`executor.py` validates step IDs/dependencies, rejects cycles, enforces max
steps/tool calls, detects repeated `(tool,args)`, applies timeout, records
`ToolResult`, propagates tenant context, and stops on failure/insufficiency.
Handlers call only application services. There is no arbitrary SQL, shell,
filesystem, Python, or HTTP tool.

`service.py` collects tool evidence. `synthesis.py` merges selected contract and
legal namespaces, applies the global generation top-K/context budget, calls the
provider, parses JSON, and runs both validators. Tool output is data; it is not
instructions. Full registries may remain in execution diagnostics, but only
selected evidence is sent to final synthesis.

This design trades flexible planning for auditability, bounded cost, and a small
attack surface. It currently has no durable agent-run/conversation persistence.

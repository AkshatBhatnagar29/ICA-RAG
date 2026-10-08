from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel

from app.services.agents.models import AgentContext, ToolResult


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    input_model: type[BaseModel]
    handler: Callable[[BaseModel, AgentContext], Awaitable[ToolResult]]
    description: str


class ToolRegistry:
    def __init__(self, tools: list[RegisteredTool] | None = None) -> None:
        self._tools = {tool.name: tool for tool in (tools or [])}

    def register(self, tool: RegisteredTool) -> None:
        if not tool.name or tool.name in self._tools:
            raise ValueError("tool name is empty or already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValueError("unknown agent tool") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

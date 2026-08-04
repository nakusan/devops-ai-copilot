"""MCP 领域模型。"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class ToolCallSpec(BaseModel):
    """关键词解析后的一次 tool 调用意图。"""

    server: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """规范化 MCP 调用结果，供 ToolNode / Synthesize 使用。"""

    success: bool
    server: str
    tool: str
    data: dict[str, Any] | list[Any] | str | None = None
    error: str | None = None
    latency_ms: int | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)

    def to_prompt_text(self) -> str:
        if not self.success:
            return f"[Tool {self.tool} 失败: {self.error}]"
        return json.dumps(self.data, ensure_ascii=False)

    def to_state_dict(self) -> dict[str, Any]:
        """兼容既有 prompt_builder：优先 result，失败时带 error。"""
        out: dict[str, Any] = {
            "tool": self.tool,
            "server": self.server,
            "arguments": self.arguments,
            "success": self.success,
            "latency_ms": self.latency_ms,
        }
        if self.success:
            out["result"] = self.data if self.data is not None else {}
        else:
            out["result"] = {"error": self.error}
            out["error"] = self.error
        return out

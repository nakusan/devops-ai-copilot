"""ToolNode — 经 MCP Client 调用 Mock/真实 Tool（设计 6.5 / 6.6）。"""

from __future__ import annotations

import logging
from typing import Any

from app.graph.state import DiagnosisState
from app.mcp.client import mcp_client
from app.mcp.resolver import resolve_tool_calls

logger = logging.getLogger(__name__)


async def tool_node(state: DiagnosisState) -> dict[str, Any]:
    """enable_mcp → 关键词解析 → McpClient.call_tool → tool_results / tool_calls。

    失败不抛崩图：写入带 error 的结果，由 Synthesize/LLM 降级说明。
    """
    cfg = state.get("agent_config") or {}
    if not cfg.get("enable_mcp", True):
        return {"tool_results": [], "tool_calls": []}

    calls = resolve_tool_calls(state.get("user_message", ""), cfg)
    results: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    trace_id = state.get("trace_id")

    for call in calls:
        res = await mcp_client.call_tool(
            server=call.server,
            name=call.tool,
            arguments=call.arguments,
            trace_id=trace_id,
        )
        state_dict = res.to_state_dict()
        results.append(state_dict)
        tool_calls.append(
            {
                "tool": res.tool,
                "server": res.server,
                "arguments": res.arguments,
                "result": state_dict.get("result"),
                "success": res.success,
                "error": res.error,
            }
        )

    logger.info(
        "tool_node done trace_id=%s calls=%d",
        trace_id,
        len(results),
        extra={"trace_id": trace_id or "", "event": "mcp.tool_node.done"},
    )
    return {"tool_results": results, "tool_calls": tool_calls}

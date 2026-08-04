"""ToolNode 单测。"""

from __future__ import annotations

import pytest

from app.graph.nodes.tool import tool_node
from app.graph.state import DiagnosisState


def _state(msg: str, *, enable_mcp: bool = True) -> DiagnosisState:
    return {  # type: ignore[return-value]
        "trace_id": "t-tool",
        "session_id": "s1",
        "user_message": msg,
        "history": [],
        "agent_config": {"enable_mcp": enable_mcp, "mcp_servers": ["prometheus"]},
        "user_context": {"user_id": 1, "team_id": 1},
        "intent": "tool",
        "retrieved_chunks": [],
        "citations": [],
        "tool_results": [],
        "tool_calls": [],
        "analysis_summary": None,
        "llm_messages": [],
        "error": None,
    }


@pytest.mark.asyncio
async def test_tool_node_disabled() -> None:
    out = await tool_node(_state("当前连接数", enable_mcp=False))
    assert out["tool_results"] == []
    assert out["tool_calls"] == []


@pytest.mark.asyncio
async def test_tool_node_connection_via_mcp() -> None:
    out = await tool_node(_state("当前连接数正常吗？"))
    assert len(out["tool_results"]) >= 1
    result = out["tool_results"][0].get("result") or {}
    assert result.get("db_connections") == 85 or result.get("value") == 85

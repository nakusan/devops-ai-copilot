"""ToolNode — MVP Mock 固定指标（Phase 5 替换为真实 MCP）。"""

from typing import Any

from app.graph.state import DiagnosisState


async def tool_node(state: DiagnosisState) -> dict[str, Any]:
    """根据用户问题关键词返回 Mock 实时数据。

    TODO(Phase-5/W11): 真实 MCP ToolNode — MCP Client/Server 未实现 — 接 McpClient.call_tool()
    """
    cfg = state.get("agent_config") or {}
    if not cfg.get("enable_mcp", True):
        return {"tool_results": [], "tool_calls": []}

    msg = state["user_message"]
    results: list[dict[str, Any]] = []

    # MVP：关键词 → 固定 Prometheus Mock 查询
    if "连接数" in msg or "DB" in msg.upper():
        mock_value = {"db_connections": 85, "unit": "count", "status": "normal"}
        results.append(
            {
                "tool": "prometheus_query",
                "arguments": {"query": "db_connections"},
                "result": mock_value,
            }
        )
    elif "CPU" in msg.upper():
        results.append(
            {
                "tool": "prometheus_query",
                "arguments": {"query": "cpu_usage_percent"},
                "result": {"cpu_usage_percent": 42.5, "status": "normal"},
            }
        )
    elif "QPS" in msg.upper():
        results.append(
            {
                "tool": "prometheus_query",
                "arguments": {"query": "http_qps"},
                "result": {"http_qps": 1250, "status": "normal"},
            }
        )
    else:
        # 通用 Mock：避免 tool 路径完全空结果
        results.append(
            {
                "tool": "prometheus_query",
                "arguments": {"query": "generic_metric"},
                "result": {"value": "mock_ok", "note": "MVP Mock 数据"},
            }
        )

    tool_calls = [
        {"tool": r["tool"], "arguments": r.get("arguments"), "result": r["result"]} for r in results
    ]
    return {"tool_results": results, "tool_calls": tool_calls}

"""Prometheus Mock MCP Server（stdio）— 设计 6.6 §3.6.1。

使用 mcp 2.x MCPServer API；启动：python -m app.mcp.mock_servers.prometheus_mock_server
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server import MCPServer

MOCK_DATA: dict[str, dict[str, Any]] = {
    "db_connections": {"value": 85, "threshold": 100, "unit": "connections", "status": "normal"},
    "service_p99_latency": {"value": 0.42, "unit": "seconds", "status": "normal"},
    "jvm_heap_used": {"value": 512, "unit": "MB", "status": "normal"},
    "cpu_usage_percent": {"cpu_usage_percent": 42.5, "status": "normal"},
    "http_qps": {"http_qps": 1250, "status": "normal"},
}

server = MCPServer("prometheus-mock")


@server.tool(
    name="prometheus_query",
    description="Query instant prometheus metric by enum key",
)
def prometheus_query(query: str) -> dict[str, Any]:
    """按枚举 key 返回 Mock 指标；未知 key 返回 error 字段。"""
    data = MOCK_DATA.get(query, {"error": "unknown query key", "query": query})
    # 兼容 prompt / 验收：db_connections 同时暴露顶层字段
    if query == "db_connections" and "value" in data:
        return {**data, "db_connections": data["value"]}
    return dict(data)


def main() -> None:
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()

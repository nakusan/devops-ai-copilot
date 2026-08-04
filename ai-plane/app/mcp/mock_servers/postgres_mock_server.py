"""Postgres Readonly Mock MCP Server（stdio）— 设计 6.6 §3.6.2。"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server import MCPServer

server = MCPServer("postgres-readonly-mock")


@server.tool(
    name="readonly_sql",
    description="Execute whitelisted read-only SQL (MVP returns fixed mock)",
)
def readonly_sql(sql: str) -> dict[str, Any]:
    """MVP：忽略 SQL 细节，返回固定结构。"""
    _ = sql  # 参数由 Client 白名单校验；此处仅演示协议
    return {"active_connections": 42, "max_connections": 200}


def main() -> None:
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()

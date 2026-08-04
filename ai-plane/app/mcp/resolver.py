"""MVP 关键词 → ToolCallSpec（设计 6.6 §3.7）。LLM function calling 留 V1.1。"""

from __future__ import annotations

import re

from app.mcp.config import get_active_servers
from app.mcp.models import ToolCallSpec

_CONN = re.compile(r"连接数|数据库连接|DB连接", re.I)
_LATENCY = re.compile(r"延迟|P99|p99", re.I)
_CPU = re.compile(r"CPU|cpu", re.I)
_QPS = re.compile(r"QPS|qps", re.I)
_PG = re.compile(r"pg_stat|activity|会话数|会话", re.I)


def resolve_tool_calls(user_message: str, agent_config: dict | None) -> list[ToolCallSpec]:
    servers = set(get_active_servers(agent_config))
    calls: list[ToolCallSpec] = []

    if "prometheus" in servers:
        if _CONN.search(user_message):
            calls.append(
                ToolCallSpec(
                    server="prometheus",
                    tool="prometheus_query",
                    arguments={"query": "db_connections"},
                )
            )
        elif _LATENCY.search(user_message):
            calls.append(
                ToolCallSpec(
                    server="prometheus",
                    tool="prometheus_query",
                    arguments={"query": "service_p99_latency"},
                )
            )
        elif _CPU.search(user_message):
            calls.append(
                ToolCallSpec(
                    server="prometheus",
                    tool="prometheus_query",
                    arguments={"query": "cpu_usage_percent"},
                )
            )
        elif _QPS.search(user_message):
            calls.append(
                ToolCallSpec(
                    server="prometheus",
                    tool="prometheus_query",
                    arguments={"query": "http_qps"},
                )
            )

    if "postgres-readonly" in servers and _PG.search(user_message):
        calls.append(
            ToolCallSpec(
                server="postgres-readonly",
                tool="readonly_sql",
                arguments={"sql": "SELECT count(*) AS cnt FROM pg_stat_activity"},
            )
        )

    # 已进入 tool 路径但无关键词命中：给一个默认 prometheus 查询，避免空上下文
    if not calls and "prometheus" in servers:
        calls.append(
            ToolCallSpec(
                server="prometheus",
                tool="prometheus_query",
                arguments={"query": "db_connections"},
            )
        )
    return calls

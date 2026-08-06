"""MCP Client / 白名单 / resolver 测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.mcp.client import mcp_client
from app.mcp.resolver import resolve_tool_calls
from app.mcp.whitelist import (
    ReadonlySqlArgs,
    ToolNotAllowedError,
    ensure_allowed,
    validate_arguments,
)


def test_whitelist_rejects_unknown_tool() -> None:
    with pytest.raises(ToolNotAllowedError):
        ensure_allowed("prometheus", "drop_database")


def test_prom_query_rejects_freeform() -> None:
    with pytest.raises(ValidationError):
        validate_arguments("prometheus", "prometheus_query", {"query": "up{job='api'}"})


def test_readonly_sql_rejects_delete() -> None:
    with pytest.raises(ValidationError):
        ReadonlySqlArgs(sql="DELETE FROM users")


def test_resolver_connection_keyword() -> None:
    calls = resolve_tool_calls("当前数据库连接数正常吗？", {"mcp_servers": ["prometheus"]})
    assert len(calls) == 1
    assert calls[0].tool == "prometheus_query"
    assert calls[0].arguments["query"] == "db_connections"


@pytest.mark.asyncio
async def test_mcp_list_and_call_prometheus() -> None:
    tools = await mcp_client.list_tools("prometheus")
    names = {t["name"] for t in tools}
    assert "prometheus_query" in names

    result = await mcp_client.call_tool(
        "prometheus",
        "prometheus_query",
        {"query": "db_connections"},
        trace_id="test-trace",
    )
    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data.get("db_connections") == 85 or result.data.get("value") == 85


@pytest.mark.asyncio
async def test_mcp_rejects_non_whitelist_via_call() -> None:
    result = await mcp_client.call_tool(
        "prometheus",
        "not_a_real_tool",
        {"query": "db_connections"},
    )
    assert result.success is False
    assert "TOOL_NOT_ALLOWED" in (result.error or "") or "not_a_real_tool" in (result.error or "")

"""MCP Client 门面：stdio 短连接 + list_tools / call_tool（设计 6.6 §3.4）。

MVP 采用「每次 call 独立 stdio 会话」：
- 避免 AsyncExitStack/anyio cancel scope 跨 task 复用导致的挂起
- Mock Server 子进程很轻；生产若改 SSE 再引入连接池
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from typing import Any

from mcp.client.stdio import stdio_client

from app.mcp.config import McpServerConfig, default_servers
from app.mcp.models import ToolResult
from app.mcp.whitelist import ToolNotAllowedError, validate_arguments
from app.observability.metrics import MCP_TOOL_CALLS, MCP_TOOL_LATENCY, observe_with_exemplar
from app.observability.otel import get_tracer
from mcp import ClientSession, StdioServerParameters

logger = logging.getLogger(__name__)
_tracer = get_tracer("ai-plane.mcp")


class McpClient:
    """失败返回 ToolResult(success=False)，不向图抛异常。"""

    def __init__(self) -> None:
        self._registry = default_servers()

    def reload_registry(self) -> None:
        self._registry = default_servers()

    async def list_tools(self, server: str) -> list[dict[str, Any]]:
        async with self._session(server) as session:
            result = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": getattr(t, "inputSchema", None)
                    or getattr(t, "input_schema", None),
                }
                for t in result.tools
            ]

    async def call_tool(
        self,
        server: str,
        name: str,
        arguments: dict[str, Any],
        *,
        trace_id: str | None = None,
    ) -> ToolResult:
        started = time.perf_counter()
        with _tracer.start_as_current_span("mcp.tool") as span:
            span.set_attribute("mcp.server", server)
            span.set_attribute("mcp.tool", name)
            if trace_id:
                span.set_attribute("copilot.trace_id", trace_id)

            try:
                validated = validate_arguments(server, name, arguments)
            except ToolNotAllowedError as ex:
                return self._fail(server, name, arguments, started, "TOOL_NOT_ALLOWED", str(ex))
            except Exception as ex:  # noqa: BLE001
                return self._fail(server, name, arguments, started, "INVALID_ARGS", str(ex)[:200])

            cfg = self._registry.get(server)
            if cfg is None or not cfg.enabled:
                return self._fail(server, name, validated, started, "SERVER_DISABLED", server)

            timeout = cfg.timeout_seconds
            try:
                async with self._session(server) as session:
                    raw = await asyncio.wait_for(
                        session.call_tool(name, validated),
                        timeout=timeout,
                    )
                data = self._parse_content(raw)
                latency_ms = int((time.perf_counter() - started) * 1000)
                observe_with_exemplar(
                    MCP_TOOL_LATENCY.labels(server=server, tool=name),
                    time.perf_counter() - started,
                )
                MCP_TOOL_CALLS.labels(server=server, tool=name, status="ok").inc()
                # 成功不打日志：ToolNode 的 12.工具 已汇总 ok/err，
                # 单次延迟有 MCP_TOOL_LATENCY 指标与 mcp.tool span。失败见 _fail。
                return ToolResult(
                    success=True,
                    server=server,
                    tool=name,
                    data=data,
                    latency_ms=latency_ms,
                    arguments=validated,
                )
            except TimeoutError:
                return self._fail(server, name, validated, started, "MCP_TIMEOUT", "MCP_TIMEOUT")
            except Exception as ex:  # noqa: BLE001
                logger.exception(
                    "mcp_call_failed server=%s tool=%s",
                    server,
                    name,
                    extra={"trace_id": trace_id or ""},
                )
                return self._fail(server, name, validated, started, "MCP_ERROR", str(ex)[:200])

    def _fail(
        self,
        server: str,
        name: str,
        arguments: dict[str, Any],
        started: float,
        code: str,
        message: str,
    ) -> ToolResult:
        latency_ms = int((time.perf_counter() - started) * 1000)
        observe_with_exemplar(
            MCP_TOOL_LATENCY.labels(server=server, tool=name),
            time.perf_counter() - started,
        )
        MCP_TOOL_CALLS.labels(server=server, tool=name, status="error").inc()
        logger.warning(
            "event=mcp.tool.call server=%s tool=%s success=false error=%s latency_ms=%s",
            server,
            name,
            code,
            latency_ms,
        )
        return ToolResult(
            success=False,
            server=server,
            tool=name,
            error=code if code == "MCP_TIMEOUT" else message,
            latency_ms=latency_ms,
            arguments=arguments,
        )

    def _session(self, server: str):
        cfg = self._registry.get(server)
        if cfg is None:
            raise RuntimeError(f"unknown mcp server: {server}")
        return _StdioSession(cfg)

    @staticmethod
    def _parse_content(raw: Any) -> dict[str, Any] | list[Any] | str | None:
        """兼容 mcp 2.x CallToolResult：优先 structuredContent，再解析 text content。"""
        structured = getattr(raw, "structuredContent", None) or getattr(
            raw, "structured_content", None
        )
        if isinstance(structured, dict | list):
            return structured

        content = getattr(raw, "content", None) or raw
        texts: list[str] = []
        for item in content or []:
            text = getattr(item, "text", None)
            if text is not None:
                texts.append(text)
        if not texts:
            return structured if structured is not None else None
        joined = "\n".join(texts)
        try:
            parsed = json.loads(joined)
            return parsed  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            return joined


class _StdioSession:
    """async with 上下文：spawn Mock Server → initialize → yield ClientSession。"""

    def __init__(self, cfg: McpServerConfig) -> None:
        self._cfg = cfg
        self._cm = None
        self._session_cm = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> ClientSession:
        if self._cfg.command in {"python", "python3"}:
            command = sys.executable
        else:
            command = self._cfg.command
        params = StdioServerParameters(command=command, args=list(self._cfg.args))
        self._cm = stdio_client(params)
        read, write = await self._cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session_cm is not None:
            await self._session_cm.__aexit__(exc_type, exc, tb)
        if self._cm is not None:
            await self._cm.__aexit__(exc_type, exc, tb)


mcp_client = McpClient()

__all__ = ["McpClient", "mcp_client"]

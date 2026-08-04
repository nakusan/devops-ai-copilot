"""MCP Server 注册表与配置（设计 6.6 §3.3）。

MVP 使用 stdio 子进程 Mock Server；生产可改为 SSE URL。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import settings


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    transport: str  # stdio | sse（MVP 仅 stdio）
    command: str
    args: list[str] = field(default_factory=list)
    enabled: bool = True
    timeout_seconds: float = 5.0


def default_servers() -> dict[str, McpServerConfig]:
    """进程内默认 Mock Server 定义。"""
    timeout = settings.mcp_default_timeout_seconds
    return {
        "prometheus": McpServerConfig(
            name="prometheus",
            transport="stdio",
            command="python",
            args=["-m", "app.mcp.mock_servers.prometheus_mock_server"],
            enabled=settings.mcp_enabled,
            timeout_seconds=timeout,
        ),
        "postgres-readonly": McpServerConfig(
            name="postgres-readonly",
            transport="stdio",
            command="python",
            args=["-m", "app.mcp.mock_servers.postgres_mock_server"],
            enabled=settings.mcp_enabled,
            timeout_seconds=timeout,
        ),
    }


def get_active_servers(agent_config: dict | None) -> list[str]:
    """agent.mcp_servers ∩ 已启用配置；请求为空时用全部已启用 server。"""
    registry = default_servers()
    enabled = {name for name, cfg in registry.items() if cfg.enabled}
    cfg = agent_config or {}
    requested = cfg.get("mcp_servers") or []
    if not requested:
        return sorted(enabled)
    return sorted(enabled & set(requested))

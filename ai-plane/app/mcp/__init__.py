"""MCP 工具挂载模块（设计 6.6）。"""

from app.mcp.client import mcp_client
from app.mcp.models import ToolCallSpec, ToolResult

__all__ = ["ToolCallSpec", "ToolResult", "mcp_client"]

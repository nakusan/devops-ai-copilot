"""FanOutNode — rag_and_tool 并行：retrieve ∥ tool。"""

import asyncio
from typing import Any

from app.graph.nodes.retrieve import retrieve_node
from app.graph.nodes.tool import tool_node
from app.graph.state import DiagnosisState


async def fan_out_node(state: DiagnosisState) -> dict[str, Any]:
    """无依赖的 RAG + Tool 并行执行，总延迟 ≈ max(retrieve, tool)。"""
    retrieve_patch, tool_patch = await asyncio.gather(
        retrieve_node(state),
        tool_node(state),
    )
    merged: dict[str, Any] = {}
    merged.update(retrieve_patch)
    merged.update(tool_patch)
    return merged

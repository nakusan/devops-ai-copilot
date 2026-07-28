"""SynthesizeNode — 模式 A：仅构建 llm_messages，不在图内流式调 LLM。"""

from typing import Any

from app.graph.llm.prompt_builder import (
    build_citations_from_state,
    build_messages,
    build_tool_calls_from_state,
)
from app.graph.state import DiagnosisState


async def synthesize_node(state: DiagnosisState) -> dict[str, Any]:
    """汇总 citations/tool_calls 并准备 LLM 输入。"""
    messages = build_messages(state)
    return {
        "llm_messages": messages,
        "citations": build_citations_from_state(state),
        "tool_calls": build_tool_calls_from_state(state),
    }

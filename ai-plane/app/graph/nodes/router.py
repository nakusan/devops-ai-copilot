"""RouterNode — 规则优先的意图分类（6.5 §3.5.1）。"""

import logging
import re
from typing import Any

from app.graph.state import DiagnosisState
from app.observability.logging import chat_msg, preview
from app.observability.otel import get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer("ai-plane.graph")

# RAG：内部知识 / 错误码 / 原因排查
RAG_PATTERNS = [
    r"STATUS_\d+",
    r"错误码",
    r"为什么",
    r"原因",
    r"故障",
    r"是什么",
]

# Tool：实时指标（MVP 关键词映射，Phase 5 换 MCP）
TOOL_PATTERNS = [
    r"当前",
    r"现在",
    r"连接数",
    r"CPU",
    r"QPS",
    r"内存",
    r"正常吗",
]

# Analysis：上传文件分析结果（Phase 4 接 Java API）
ANALYSIS_PATTERNS = [
    r"分析结果",
    r"heap",
    r"上传的",
    r"dump",
]


def _matches(patterns: list[str], message: str) -> bool:
    return any(re.search(p, message, re.IGNORECASE) for p in patterns)


def router_node(state: DiagnosisState) -> dict[str, Any]:
    """判定 intent，供 conditional_edges 路由。

    优先级：analysis > rag_and_tool > tool > rag > 默认 rag/direct。
    """
    with _tracer.start_as_current_span("graph.router") as span:
        msg = state.get("user_message", "")
        cfg = state.get("agent_config") or {}
        enable_rag = cfg.get("enable_rag", True)
        enable_mcp = cfg.get("enable_mcp", True)

        rag_hit = enable_rag and _matches(RAG_PATTERNS, msg)
        tool_hit = enable_mcp and _matches(TOOL_PATTERNS, msg)

        if _matches(ANALYSIS_PATTERNS, msg):
            intent = "analysis"
        elif rag_hit and tool_hit:
            intent = "rag_and_tool"
        elif tool_hit:
            intent = "tool"
        elif rag_hit:
            intent = "rag"
        elif enable_rag:
            # 运维场景默认偏向查知识库
            intent = "rag"
        else:
            intent = "direct"

        span.set_attribute("graph.intent", intent)
        logger.info(
            chat_msg(
                "11.路由",
                f"intent={intent} ragHit={rag_hit} toolHit={tool_hit} "
                f"enableRag={enable_rag} enableMcp={enable_mcp} "
                f"user=\"{preview(msg)}\"",
            ),
            extra={"trace_id": state.get("trace_id") or ""},
        )
        # TODO(Phase-5/V1.1): LLM intent 分类 — MVP 规则优先省成本 — 规则未命中时调小模型
        return {"intent": intent}


def route_by_intent(state: DiagnosisState) -> str:
    """conditional_edges 路由函数。"""
    return state.get("intent") or "direct"

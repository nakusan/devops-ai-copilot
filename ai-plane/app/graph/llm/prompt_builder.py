"""Prompt 构建 — 将 RAG/Tool/Analysis 上下文拼进 LLM messages。"""

import json
from typing import Any

from app.graph.state import DiagnosisState

_GROUNDING_RULES = """
你必须遵守：
1. 仅基于提供的【内部知识】【实时数据】【分析结果】回答，不得编造。
2. 若上下文不足，明确说明「内部资料未覆盖」。
3. 引用知识时使用 [n] 标注。
"""


def build_messages(state: DiagnosisState) -> list[dict[str, str]]:
    """模式 A：图跑完后由 orchestrator 调用，生成 OpenAI chat messages。"""
    cfg = state.get("agent_config") or {}
    system = (cfg.get("system_prompt") or "").strip()
    system = f"{system}\n{_GROUNDING_RULES}".strip()

    context_blocks: list[str] = []

    chunks = state.get("retrieved_chunks") or []
    if not chunks:
        context_blocks.append("（无额外内部知识检索结果）")
    else:
        for i, chunk in enumerate(chunks, 1):
            title = chunk.get("document_title", "未知来源")
            score = chunk.get("score", 0.0)
            content = chunk.get("content", "")
            context_blocks.append(f"[{i}] (来源: {title}, score={score:.2f})\n{content}")

    for tool in state.get("tool_results") or []:
        tool_name = tool.get("tool", "unknown")
        result_json = json.dumps(tool.get("result", {}), ensure_ascii=False)
        context_blocks.append(f"【实时数据】{tool_name}: {result_json}")

    analysis_summary = state.get("analysis_summary")
    if analysis_summary:
        context_blocks.append(f"【文件分析结果】\n{analysis_summary}")
    elif state.get("intent") == "analysis":
        context_blocks.append("【文件分析结果】（暂无已完成的上传分析任务）")

    context_text = "\n\n".join(context_blocks)

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for h in state.get("history") or []:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append(
        {
            "role": "user",
            "content": f"上下文：\n{context_text}\n\n用户问题：{state['user_message']}",
        }
    )
    return messages


def build_citations_from_state(state: DiagnosisState) -> list[dict[str, Any]]:
    """从 state 提取 citations（优先已汇总的 citations 字段）。"""
    if state.get("citations"):
        return list(state["citations"])
    return []

def build_tool_calls_from_state(state: DiagnosisState) -> list[dict[str, Any]]:
    if state.get("tool_calls"):
        return list(state["tool_calls"])
    return [
        {"tool": t.get("tool"), "result": t.get("result")}
        for t in (state.get("tool_results") or [])
    ]

"""组装 Agent ReAct 初始 messages。"""

from __future__ import annotations

from typing import Any

_AGENT_RULES = """
你是运维诊断助手。必须遵守：
1. 需要内部知识时调用 retrieve_knowledge；问候/闲聊不要检索。
2. 需要实时指标时调用 prometheus_query 或 readonly_sql；参数必须落在工具 schema 内。
3. 需要用户上传文件的分析结果时，先 list_analysis_jobs 再 get_analysis_job。
4. 可多轮调用工具；信息足够后直接用中文回答用户。
5. 仅基于工具结果与对话上下文作答，不得编造指标或文档内容；不足时明确说明。
6. 引用知识时使用 [n] 标注（n 与检索结果顺序一致）。
""".strip()


def build_agent_messages(
    *,
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
) -> list[dict[str, Any]]:
    """system + history + 本轮 user。后续 tool 轮由 orchestrator 追加。"""
    system = (system_prompt or "").strip()
    system = f"{system}\n\n{_AGENT_RULES}".strip() if system else _AGENT_RULES
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for h in history:
        role = h.get("role") or "user"
        content = h.get("content") or ""
        if role in {"user", "assistant", "system"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages

"""LangGraph 诊断状态 — 各节点间传递的唯一上下文。"""

from typing import Any, TypedDict


class DiagnosisState(TypedDict, total=False):
    """MVP 每轮覆盖式更新；列表字段由节点整体写入，不做 reducer 追加。"""

    # --- 输入（来自 InternalChatRequest）---
    trace_id: str
    session_id: str
    user_message: str
    history: list[dict[str, str]]
    agent_config: dict[str, Any]
    user_context: dict[str, Any]

    # --- 路由 ---
    intent: str  # rag | tool | rag_and_tool | analysis | direct

    # --- 中间结果 ---
    retrieved_chunks: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    analysis_summary: str | None

    # --- 合成准备（模式 A：图内不流式 LLM）---
    llm_messages: list[dict[str, str]]

    # --- 输出汇总 ---
    citations: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    final_answer: str
    usage: dict[str, Any]
    error: str | None


def init_state_from_request(req: Any) -> DiagnosisState:
    """从 InternalChatRequest 初始化图状态。

    约定（P7）：history 不含本轮 user_message，避免 prompt 重复。
    """
    cfg = req.agent_config
    return DiagnosisState(
        trace_id=req.trace_id,
        session_id=req.session_id,
        user_message=req.user_message,
        history=[{"role": m.role, "content": m.content} for m in req.history],
        agent_config={
            "model": cfg.model,
            "system_prompt": cfg.system_prompt,
            "enable_rag": cfg.enable_rag,
            "enable_mcp": cfg.enable_mcp,
            "rag_top_k": cfg.rag_top_k,
            "rag_score_threshold": cfg.rag_score_threshold,
            "temperature": cfg.temperature,
            "max_history_messages": cfg.max_history_messages,
            "mcp_servers": cfg.mcp_servers,
            "llm_timeout_seconds": cfg.llm_timeout_seconds,
        },
        user_context={
            "user_id": req.user_context.user_id,
            "team_id": req.user_context.team_id,
        },
        retrieved_chunks=[],
        tool_results=[],
        analysis_summary=None,
        citations=[],
        tool_calls=[],
        final_answer="",
        usage={},
        error=None,
    )

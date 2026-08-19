"""LLM 埋点纯函数：usage 解析 / 暂存 / 累加，不含 span 生命周期。

与 LlmObserver 分工：
- instrumentation：无状态工具函数 + 模块级 usage 暂存（pop_stream_usage 契约）
- LlmObserver：一次调用的 span / TTFB 上下文

orchestrator 仍从 llm_client 导入 pop_stream_usage / merge_usage（再导出），
避免改动调用方。
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 模块级 usage 暂存：stream / stream_text_chunks 结束后由 orchestrator pop。
# 保持与原 llm_client._last_usage 相同语义；勿改成请求级对象以免破坏契约。
# ---------------------------------------------------------------------------
_last_usage: dict[str, Any] = {}


def prompt_chars(messages: list[dict[str, Any]]) -> int:
    """估算喂给模型的上下文体积（日志用，非精确 tokenizer）。"""
    return sum(len(str(m.get("content") or "")) for m in messages)


def parse_openai_usage(usage_obj: Any | None) -> dict[str, Any]:
    """OpenAI SDK usage → 项目内 camelCase dict；无 usage 时返回空 dict。"""
    if usage_obj is None:
        return {}
    return {
        "promptTokens": usage_obj.prompt_tokens or 0,
        "completionTokens": usage_obj.completion_tokens or 0,
        "totalTokens": usage_obj.total_tokens or 0,
    }


def set_usage_span_attrs(span: Any, usage: dict[str, Any]) -> None:
    """把 usage 写入 OTel gen_ai.usage.*（与原先 _set_usage_attrs 一致）。"""
    if not usage:
        return
    if "promptTokens" in usage:
        span.set_attribute("gen_ai.usage.input_tokens", int(usage["promptTokens"]))
    if "completionTokens" in usage:
        span.set_attribute("gen_ai.usage.output_tokens", int(usage["completionTokens"]))


def attach_usage(usage: dict[str, Any]) -> None:
    """挂起最近一次流式 usage，供 pop_stream_usage 读取。"""
    global _last_usage
    _last_usage = usage


def pop_stream_usage() -> dict[str, Any]:
    """读取并清空最近一次 stream / 切片路径写入的 usage。"""
    global _last_usage
    usage = _last_usage
    _last_usage = {}
    return usage


def merge_usage(total: dict[str, Any], part: dict[str, Any]) -> dict[str, Any]:
    """累加多轮 LLM usage（规划轮 + 最终轮）。"""
    if not part:
        return total
    for key in ("promptTokens", "completionTokens", "totalTokens"):
        total[key] = int(total.get(key) or 0) + int(part.get(key) or 0)
    return total


def estimate_token_usage(*, prompt_chars_n: int, produced_chars: int) -> dict[str, Any]:
    """Mock / 切片路径粗估 token（约 4 字符 ≈ 1 token），与原先算法一致。"""
    prompt_tokens = max(1, prompt_chars_n // 4)
    completion_tokens = max(1, produced_chars // 4)
    return {
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
        "totalTokens": prompt_tokens + completion_tokens,
    }

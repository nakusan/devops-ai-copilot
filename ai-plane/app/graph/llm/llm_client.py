"""OpenAI 兼容 LLM 流式客户端（模式 A：图外 stream）。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, RateLimitError

from app.config import settings
from app.graph.models.stream_event import StreamEvent, error_event, token_event

logger = logging.getLogger(__name__)


class LlmStreamResult:
    """stream_chat 结束后汇总，供 done 事件使用。"""

    def __init__(self) -> None:
        self.full_text = ""
        self.usage: dict[str, Any] = {}
        self.cancelled = False


async def stream_chat(
    messages: list[dict[str, str]],
    *,
    model: str,
    temperature: float,
    cancel_event: asyncio.Event,
    timeout_seconds: int | None = None,
    user_message: str = "",
) -> AsyncIterator[StreamEvent]:
    """流式生成 token 事件；结束时 usage 写入 LlmStreamResult（通过 generator attribute）。"""
    mode = settings.effective_llm_mode()
    timeout = timeout_seconds or settings.llm_timeout_seconds

    if mode == "mock":
        async for evt in _mock_stream(messages, model, cancel_event, user_message):
            yield evt
        return

    # TODO(V1): astream_events 模式 B — 设计书 V1 图内流式优化项
    async for evt in _openai_stream(messages, model, temperature, cancel_event, timeout):
        yield evt


async def _mock_stream(
    messages: list[dict[str, str]],
    model: str,
    cancel_event: asyncio.Event,
    user_message: str,
) -> AsyncIterator[StreamEvent]:
    """复用 Phase 2 Mock 切片逻辑，基于最终 prompt 回显摘要。"""
    chunk_size = max(1, settings.llm_mock_chunk_size)
    delay = settings.llm_mock_delay_ms / 1000.0
    prefix = f"[mock:{model}] "
    # 优先用原始 user_message，否则取最后一条 user 内容
    body = user_message or _last_user_content(messages)
    full = prefix + body
    produced = 0

    for i in range(0, len(full), chunk_size):
        if cancel_event.is_set():
            yield error_event("CANCELLED", "生成已取消")
            return
        piece = full[i : i + chunk_size]
        produced += len(piece)
        yield token_event(piece)
        if delay > 0:
            await asyncio.sleep(delay)

    if cancel_event.is_set():
        yield error_event("CANCELLED", "生成已取消")
        return

    # Mock usage 粗估
    prompt_tokens = max(1, sum(len(m.get("content", "")) for m in messages) // 4)
    completion_tokens = max(1, produced // 4)
    _attach_usage(
        {
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": prompt_tokens + completion_tokens,
        }
    )


async def _openai_stream(
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    cancel_event: asyncio.Event,
    timeout: int,
) -> AsyncIterator[StreamEvent]:
    api_key = settings.llm_api_key
    if not api_key:
        yield error_event("LLM_CONFIG", "LLM_API_KEY 未配置")
        return

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=settings.llm_base_url,
        timeout=float(timeout),
    )

    async def _run_stream() -> AsyncIterator[StreamEvent]:
        nonlocal client
        attempts = 0
        while attempts < 2:
            attempts += 1
            try:
                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    stream=True,
                    stream_options={"include_usage": True},
                )
                usage: dict[str, Any] = {}
                async for chunk in stream:
                    if cancel_event.is_set():
                        yield error_event("CANCELLED", "生成已取消")
                        return
                    if chunk.usage is not None:
                        usage = {
                            "promptTokens": chunk.usage.prompt_tokens or 0,
                            "completionTokens": chunk.usage.completion_tokens or 0,
                            "totalTokens": chunk.usage.total_tokens or 0,
                        }
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yield token_event(delta)
                _attach_usage(usage)
                return
            except RateLimitError:
                if attempts >= 2:
                    yield error_event("LLM_RATE_LIMIT", "LLM 限流，请稍后重试")
                    return
                await asyncio.sleep(1.0)
            except TimeoutError:
                yield error_event("LLM_TIMEOUT", "LLM 请求超时")
                return
            except Exception as ex:  # noqa: BLE001
                logger.exception("LLM stream failed")
                yield error_event("AGENT_ERROR", str(ex))
                return

    try:
        async for evt in _run_stream():
            yield evt
    except TimeoutError:
        yield error_event("LLM_TIMEOUT", "LLM 请求超时")


def _last_user_content(messages: list[dict[str, str]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


# 模块级临时 usage 挂载（stream_chat 单次调用内读取）
_last_usage: dict[str, Any] = {}


def _attach_usage(usage: dict[str, Any]) -> None:
    global _last_usage
    _last_usage = usage


def pop_stream_usage() -> dict[str, Any]:
    """读取并清空最近一次 stream 的 usage。"""
    global _last_usage
    usage = _last_usage
    _last_usage = {}
    return usage

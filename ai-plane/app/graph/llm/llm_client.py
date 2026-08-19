"""OpenAI 兼容 LLM 客户端。

模式 A：
- 规划轮：非流式 complete（可带 tools）→ 解析 tool_calls 或 content
- 最终轮：流式 stream_chat 推 token；若规划轮已有 content 则本地切片推送（不重复打模型）

横切关注点（span / TTFB / usage）委托给：
- ``app.observability.llm_observer.LlmObserver``
- ``app.graph.llm.instrumentation``（纯函数）

本文件只保留：构造请求、解析 choice/chunk、cancel、yield 业务事件。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI, RateLimitError

from app.config import settings
from app.graph.llm.instrumentation import (
    attach_usage,
    estimate_token_usage,
    merge_usage,
    parse_openai_usage,
    pop_stream_usage,
    prompt_chars,
)
from app.graph.models.stream_event import StreamEvent, error_event, token_event
from app.observability.llm_observer import LlmObserver
from app.observability.logging import chat_msg, preview

logger = logging.getLogger(__name__)

# 对外再导出，保持 orchestrator 等调用方 import 路径不变
__all__ = [
    "LlmTurnResult",
    "complete_with_tools",
    "merge_usage",
    "pop_stream_usage",
    "stream_chat",
    "stream_text_chunks",
]


@dataclass
class LlmTurnResult:
    """规划轮（非流式）结果。"""

    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False
    error_event: StreamEvent | None = None


async def complete_with_tools(
    messages: list[dict[str, Any]],
    *,
    model: str,
    temperature: float,
    cancel_event: asyncio.Event,
    tools: list[dict[str, Any]] | None = None,
    timeout_seconds: int | None = None,
) -> LlmTurnResult:
    """非流式一轮：带 tools 时可能返回 tool_calls，否则返回 content。"""
    if cancel_event.is_set():
        return LlmTurnResult(cancelled=True)

    mode = settings.effective_llm_mode()
    timeout = timeout_seconds or settings.llm_timeout_seconds
    logger.debug(
        chat_msg(
            "13.LLM",
            f"mode={mode} phase=plan model={model} temp={temperature} "
            f"msgCount={len(messages)} promptChars={prompt_chars(messages)} "
            f"tools={len(tools or [])} timeoutSec={timeout}",
        )
    )

    if mode == "mock":
        return _mock_complete(messages, tools)

    api_key = settings.llm_api_key
    if not api_key:
        return LlmTurnResult(error_event=error_event("LLM_CONFIG", "LLM_API_KEY 未配置"))

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=settings.llm_base_url,
        timeout=float(timeout),
    )

    attempts = 0
    while attempts < 2:
        attempts += 1
        if cancel_event.is_set():
            return LlmTurnResult(cancelled=True)
        try:
            # 埋点切片：span / usage attrs；业务只负责 create + 解析 message
            with LlmObserver.plan(model, temperature).activate() as obs:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "extra_body": {"thinking": {"type": "disabled"}},
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                resp = await client.chat.completions.create(**kwargs)
                choice = resp.choices[0].message if resp.choices else None
                usage = parse_openai_usage(resp.usage)
                obs.record_usage(usage)

                tool_calls = _parse_tool_calls(choice)
                content = (choice.content if choice else None) or None
                obs.set_tool_call_count(len(tool_calls))
                return LlmTurnResult(content=content, tool_calls=tool_calls, usage=usage)
        except RateLimitError:
            if attempts >= 2:
                return LlmTurnResult(
                    error_event=error_event("LLM_RATE_LIMIT", "LLM 限流，请稍后重试")
                )
            await asyncio.sleep(1.0)
        except TimeoutError:
            return LlmTurnResult(error_event=error_event("LLM_TIMEOUT", "LLM 请求超时"))
        except Exception as ex:  # noqa: BLE001
            logger.exception(
                chat_msg("13.LLM", f"phase=plan status=error error=\"{preview(str(ex))}\"")
            )
            return LlmTurnResult(error_event=error_event("AGENT_ERROR", str(ex)))

    return LlmTurnResult(error_event=error_event("LLM_RATE_LIMIT", "LLM 限流，请稍后重试"))


async def stream_chat(
    messages: list[dict[str, Any]],
    *,
    model: str,
    temperature: float,
    cancel_event: asyncio.Event,
    timeout_seconds: int | None = None,
    user_message: str = "",
) -> AsyncIterator[StreamEvent]:
    """流式生成 token 事件（最终回答轮，不带 tools）。"""
    mode = settings.effective_llm_mode()
    timeout = timeout_seconds or settings.llm_timeout_seconds
    logger.debug(
        chat_msg(
            "13.LLM",
            f"mode={mode} phase=stream model={model} temp={temperature} "
            f"msgCount={len(messages)} promptChars={prompt_chars(messages)} "
            f"timeoutSec={timeout}",
        )
    )

    if mode == "mock":
        async for evt in _mock_stream(
            messages, model, temperature, cancel_event, user_message
        ):
            yield evt
        return

    async for evt in _openai_stream(messages, model, temperature, cancel_event, timeout):
        yield evt


async def stream_text_chunks(
    text: str,
    *,
    cancel_event: asyncio.Event,
    usage: dict[str, Any] | None = None,
) -> AsyncIterator[StreamEvent]:
    """把已拿到的完整答案切片推送，避免规划轮无 tool_calls 时再打一次模型。

    无 OTel span（与原先一致）；仅采 TTFB + attach usage。
    """
    chunk_size = max(1, settings.llm_mock_chunk_size)
    delay = settings.llm_mock_delay_ms / 1000.0
    # 无 span：只用 observer 的时钟与 TTFB histogram
    obs = LlmObserver.stream(model="prefetch", temperature=0.0)
    obs.begin_clock()
    for i in range(0, len(text), chunk_size):
        if cancel_event.is_set():
            yield error_event("CANCELLED", "生成已取消")
            return
        obs.mark_first_token()
        yield token_event(text[i : i + chunk_size])
        if delay > 0:
            await asyncio.sleep(delay)
    if usage:
        attach_usage(usage)
    elif text:
        # 与原先一致：切片路径无真实 prompt，usage 只估 completion
        n = max(1, len(text) // 4)
        attach_usage({"promptTokens": 0, "completionTokens": n, "totalTokens": n})


def _mock_complete(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
) -> LlmTurnResult:
    """默认 mock：不调工具，返回简短 content（测试可 patch 本函数或 complete_with_tools）。"""
    _ = tools
    body = _last_user_content(messages) or "ok"
    # usage 公式与改造前保持一致，避免测试/配额侧漂移
    return LlmTurnResult(
        content=f"[mock-plan] {body}",
        tool_calls=[],
        usage={
            "promptTokens": max(1, prompt_chars(messages) // 4),
            "completionTokens": max(1, len(body) // 4),
            "totalTokens": max(1, (len(body) + 8) // 4),
        },
    )


async def _mock_stream(
    messages: list[dict[str, Any]],
    model: str,
    temperature: float,
    cancel_event: asyncio.Event,
    user_message: str,
) -> AsyncIterator[StreamEvent]:
    """复用 Phase 2 Mock 切片逻辑。"""
    chunk_size = max(1, settings.llm_mock_chunk_size)
    delay = settings.llm_mock_delay_ms / 1000.0
    prefix = f"[mock:{model}] "
    body = user_message or _last_user_content(messages)
    full = prefix + body
    produced = 0

    with LlmObserver.stream(model, temperature, system="mock").activate() as obs:
        for i in range(0, len(full), chunk_size):
            if cancel_event.is_set():
                yield error_event("CANCELLED", "生成已取消")
                return
            piece = full[i : i + chunk_size]
            produced += len(piece)
            obs.mark_first_token()
            yield token_event(piece)
            if delay > 0:
                await asyncio.sleep(delay)

        if cancel_event.is_set():
            yield error_event("CANCELLED", "生成已取消")
            return

        usage = estimate_token_usage(
            prompt_chars_n=prompt_chars(messages),
            produced_chars=produced,
        )
        obs.finish_with_usage(usage)


async def _openai_stream(
    messages: list[dict[str, Any]],
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
        attempts = 0
        while attempts < 2:
            attempts += 1
            try:
                with LlmObserver.stream(model, temperature).activate() as obs:
                    stream = await client.chat.completions.create(
                        model=model,
                        messages=messages,  # type: ignore[arg-type]
                        temperature=temperature,
                        stream=True,
                        stream_options={"include_usage": True},
                        extra_body={"thinking": {"type": "disabled"}},
                    )
                    usage: dict[str, Any] = {}
                    async for chunk in stream:
                        if cancel_event.is_set():
                            yield error_event("CANCELLED", "生成已取消")
                            return
                        # usage 可能出现在末尾 chunk
                        if chunk.usage is not None:
                            usage = parse_openai_usage(chunk.usage)
                        delta = (
                            chunk.choices[0].delta.content if chunk.choices else None
                        )
                        if delta:
                            obs.mark_first_token()
                            yield token_event(delta)
                    obs.finish_with_usage(usage)
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
                logger.exception(
                    chat_msg(
                        "13.LLM",
                        f"phase=stream status=error error=\"{preview(str(ex))}\"",
                    )
                )
                yield error_event("AGENT_ERROR", str(ex))
                return

    try:
        async for evt in _run_stream():
            yield evt
    except TimeoutError:
        yield error_event("LLM_TIMEOUT", "LLM 请求超时")


def _parse_tool_calls(choice: Any) -> list[dict[str, Any]]:
    """从 assistant message 解析 OpenAI tool_calls → 内部 dict 列表。"""
    tool_calls: list[dict[str, Any]] = []
    if not choice or not choice.tool_calls:
        return tool_calls
    for tc in choice.tool_calls:
        fn = tc.function
        args_raw = fn.arguments or "{}"
        try:
            # 分行写避免 E501；SIM108 三元式在此可读性更差
            if isinstance(args_raw, str):  # noqa: SIM108
                args = json.loads(args_raw)
            else:
                args = dict(args_raw)
        except json.JSONDecodeError:
            args = {"_raw": args_raw}
        tool_calls.append(
            {
                "id": tc.id or fn.name,
                "name": fn.name,
                "arguments": args,
            }
        )
    return tool_calls


def _last_user_content(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content") or "")
    return ""

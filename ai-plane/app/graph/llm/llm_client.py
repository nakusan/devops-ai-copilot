"""OpenAI 兼容 LLM 客户端。

模式 A：
- 规划轮：非流式 complete（可带 tools）→ 解析 tool_calls 或 content
- 最终轮：流式 stream_chat 推 token；若规划轮已有 content 则本地切片推送（不重复打模型）
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI, RateLimitError

from app.config import settings
from app.graph.models.stream_event import StreamEvent, error_event, token_event
from app.observability.logging import chat_msg
from app.observability.metrics import LLM_TTFB, observe_with_exemplar
from app.observability.otel import get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer("ai-plane.llm")


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
    prompt_chars = sum(len(str(m.get("content") or "")) for m in messages)
    logger.info(
        chat_msg(
            "13.LLM",
            f"mode={mode} phase=plan model={model} temp={temperature} "
            f"msgCount={len(messages)} promptChars={prompt_chars} "
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
            with _tracer.start_as_current_span("llm.plan") as span:
                span.set_attribute("gen_ai.system", "openai_compatible")
                span.set_attribute("gen_ai.request.model", model)
                span.set_attribute("gen_ai.request.temperature", float(temperature))
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
                usage = {}
                if resp.usage is not None:
                    usage = {
                        "promptTokens": resp.usage.prompt_tokens or 0,
                        "completionTokens": resp.usage.completion_tokens or 0,
                        "totalTokens": resp.usage.total_tokens or 0,
                    }
                    _set_usage_attrs(span, usage)

                tool_calls: list[dict[str, Any]] = []
                if choice and choice.tool_calls:
                    for tc in choice.tool_calls:
                        fn = tc.function
                        args_raw = fn.arguments or "{}"
                        try:
                            if isinstance(args_raw, str):
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
                content = (choice.content if choice else None) or None
                span.set_attribute("llm.tool_calls", len(tool_calls))
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
            logger.exception("LLM plan failed")
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
    prompt_chars = sum(len(str(m.get("content") or "")) for m in messages)
    logger.info(
        chat_msg(
            "13.LLM",
            f"mode={mode} phase=stream model={model} temp={temperature} "
            f"msgCount={len(messages)} promptChars={prompt_chars} timeoutSec={timeout}",
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
    """把已拿到的完整答案切片推送，避免规划轮无 tool_calls 时再打一次模型。"""
    chunk_size = max(1, settings.llm_mock_chunk_size)
    delay = settings.llm_mock_delay_ms / 1000.0
    ttfb_started = time.perf_counter()
    first = True
    for i in range(0, len(text), chunk_size):
        if cancel_event.is_set():
            yield error_event("CANCELLED", "生成已取消")
            return
        if first:
            observe_with_exemplar(LLM_TTFB, time.perf_counter() - ttfb_started)
            first = False
        yield token_event(text[i : i + chunk_size])
        if delay > 0:
            await asyncio.sleep(delay)
    if usage:
        _attach_usage(usage)
    elif text:
        _attach_usage(
            {
                "promptTokens": 0,
                "completionTokens": max(1, len(text) // 4),
                "totalTokens": max(1, len(text) // 4),
            }
        )


def _mock_complete(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
) -> LlmTurnResult:
    """默认 mock：不调工具，返回简短 content（测试可 patch 本函数或 complete_with_tools）。"""
    _ = tools
    body = _last_user_content(messages) or "ok"
    return LlmTurnResult(
        content=f"[mock-plan] {body}",
        tool_calls=[],
        usage={
            "promptTokens": max(1, sum(len(str(m.get("content") or "")) for m in messages) // 4),
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
    ttfb_started = time.perf_counter()
    first_token = True

    with _tracer.start_as_current_span("llm.completion") as span:
        span.set_attribute("gen_ai.system", "mock")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.request.temperature", float(temperature))
        for i in range(0, len(full), chunk_size):
            if cancel_event.is_set():
                yield error_event("CANCELLED", "生成已取消")
                return
            piece = full[i : i + chunk_size]
            produced += len(piece)
            if first_token:
                ttfb = time.perf_counter() - ttfb_started
                span.set_attribute("llm.ttfb_ms", int(ttfb * 1000))
                observe_with_exemplar(LLM_TTFB, ttfb)
                first_token = False
            yield token_event(piece)
            if delay > 0:
                await asyncio.sleep(delay)

        if cancel_event.is_set():
            yield error_event("CANCELLED", "生成已取消")
            return

        prompt_tokens = max(1, sum(len(str(m.get("content") or "")) for m in messages) // 4)
        completion_tokens = max(1, produced // 4)
        usage = {
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": prompt_tokens + completion_tokens,
        }
        _set_usage_attrs(span, usage)
        _attach_usage(usage)


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
                ttfb_started = time.perf_counter()
                first_token = True
                with _tracer.start_as_current_span("llm.completion") as span:
                    span.set_attribute("gen_ai.system", "openai_compatible")
                    span.set_attribute("gen_ai.request.model", model)
                    span.set_attribute("gen_ai.request.temperature", float(temperature))
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
                        if chunk.usage is not None:
                            usage = {
                                "promptTokens": chunk.usage.prompt_tokens or 0,
                                "completionTokens": chunk.usage.completion_tokens or 0,
                                "totalTokens": chunk.usage.total_tokens or 0,
                            }
                        delta = chunk.choices[0].delta.content if chunk.choices else None
                        if delta:
                            if first_token:
                                ttfb = time.perf_counter() - ttfb_started
                                span.set_attribute("llm.ttfb_ms", int(ttfb * 1000))
                                observe_with_exemplar(LLM_TTFB, ttfb)
                                first_token = False
                            yield token_event(delta)
                    _set_usage_attrs(span, usage)
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


def _set_usage_attrs(span: Any, usage: dict[str, Any]) -> None:
    if not usage:
        return
    if "promptTokens" in usage:
        span.set_attribute("gen_ai.usage.input_tokens", int(usage["promptTokens"]))
    if "completionTokens" in usage:
        span.set_attribute("gen_ai.usage.output_tokens", int(usage["completionTokens"]))


def _last_user_content(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content") or "")
    return ""


_last_usage: dict[str, Any] = {}


def _attach_usage(usage: dict[str, Any]) -> None:
    global _last_usage
    _last_usage = usage


def pop_stream_usage() -> dict[str, Any]:
    """读取并清空最近一次 stream / plan 的 usage。"""
    global _last_usage
    usage = _last_usage
    _last_usage = {}
    return usage


def merge_usage(total: dict[str, Any], part: dict[str, Any]) -> dict[str, Any]:
    """累加多轮 LLM usage。"""
    if not part:
        return total
    for key in ("promptTokens", "completionTokens", "totalTokens"):
        total[key] = int(total.get(key) or 0) + int(part.get(key) or 0)
    return total

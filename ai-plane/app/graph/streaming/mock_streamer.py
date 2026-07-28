"""Phase 2 Mock 流式生成器：不调真实 LLM，只验证 NDJSON 管道。

将 user_message 按片切分，逐片 yield token，最后发 done（含假 usage）。
Week 6 起由 LangGraph + 真 LLM 替换本模块。
"""

import asyncio
import time
from collections.abc import AsyncIterator

from app.config import settings
from app.graph.models.internal_chat_request import InternalChatRequest
from app.graph.models.stream_event import StreamEvent, done_event, error_event, token_event


async def mock_stream(
    req: InternalChatRequest,
    cancel_event: asyncio.Event,
) -> AsyncIterator[StreamEvent]:
    """回显式 Mock：前缀说明 + 用户原文切片。"""
    started = time.perf_counter()
    prefix = f"[mock:{req.agent_config.model}] "
    full = prefix + req.user_message
    chunk = max(1, settings.llm_mock_chunk_size)
    delay = settings.llm_mock_delay_ms / 1000.0

    produced_chars = 0
    try:
        for i in range(0, len(full), chunk):
            if cancel_event.is_set():
                # 取消：不再发 token；由上层决定是否发 error。此处直接结束循环。
                break
            piece = full[i : i + chunk]
            produced_chars += len(piece)
            yield token_event(piece)
            if delay > 0:
                await asyncio.sleep(delay)

        if cancel_event.is_set():
            yield error_event("CANCELLED", "生成已取消")
            return

        latency_ms = int((time.perf_counter() - started) * 1000)
        # 假 usage：按字符粗估，便于 Java 侧练习配额累加
        prompt_tokens = max(1, len(req.user_message) // 4)
        completion_tokens = max(1, produced_chars // 4)
        yield done_event(
            {
                "intent": "direct",
                "model": req.agent_config.model,
                "latencyMs": latency_ms,
                "usage": {
                    "promptTokens": prompt_tokens,
                    "completionTokens": completion_tokens,
                    "totalTokens": prompt_tokens + completion_tokens,
                },
                "citations": [],
                "toolCalls": [],
            }
        )
    except Exception as ex:  # noqa: BLE001 — 流末尾统一 error 事件，避免挂死连接
        yield error_event("AGENT_ERROR", str(ex))

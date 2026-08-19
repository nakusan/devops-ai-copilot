"""内部聊天流式路由（Java → Python）。"""

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import ServiceTokenDep
from app.config import settings
from app.graph.models.internal_chat_request import CancelRequest, InternalChatRequest
from app.graph.orchestrator import run_diagnosis_stream
from app.graph.streaming.cancel_registry import cancel_registry
from app.graph.streaming.mock_streamer import mock_stream
from app.observability.logging import chat_msg, preview

router = APIRouter(prefix="/internal/v1/chat", tags=["internal-chat"])
logger = logging.getLogger(__name__)


@router.post("/stream")
async def chat_stream(
    req: InternalChatRequest,
    _: ServiceTokenDep,
) -> StreamingResponse:
    """返回 application/x-ndjson：每行一个 StreamEvent JSON。

    为何不用 SSE 对内：Java WebClient 按行解析 NDJSON 更简单，且与对外 SSE 职责分离（P8）。

    CHAT_BACKEND=orchestrator（默认）走 ReAct；=mock 回退 Phase 2 Mock（排障用）。
    """

    history_count = len(req.history or [])
    cfg = req.agent_config
    logger.info(
        chat_msg(
            "10.接收请求",
            f"sessionId={req.session_id} backend={settings.chat_backend} "
            f"model={cfg.model} historyCount={history_count} "
            f"enableRag={cfg.enable_rag} enableMcp={cfg.enable_mcp} "
            f"userChars={len(req.user_message or '')} "
            f"user=\"{preview(req.user_message)}\"",
        ),
        extra={"trace_id": req.trace_id or "", "event": "chat.stream.recv"},
    )

    cancel_event = cancel_registry.register(req.session_id)

    async def event_generator() -> AsyncIterator[str]:
        started = time.perf_counter()
        token_n = 0
        answer_chars = 0
        ttfb_ms = -1
        done: dict[str, Any] = {}
        # 兜底 aborted：既无 done 也无 error 就走到 finally，说明 Java 侧提前断流
        outcome = "aborted"
        try:
            if settings.chat_backend == "mock":
                stream = mock_stream(req, cancel_event)
            else:
                stream = run_diagnosis_stream(req, cancel_event)
            async for event in stream:
                if event.type == "token":
                    token_n += 1
                    answer_chars += len(event.text or "")
                    if ttfb_ms < 0:
                        ttfb_ms = int((time.perf_counter() - started) * 1000)
                elif event.type == "done":
                    outcome = "done"
                    done = event.done or {}
                elif event.type == "error":
                    outcome = "error"
                    logger.warning(
                        chat_msg(
                            "14.错误",
                            f"sessionId={req.session_id} error={event.error}",
                        ),
                        extra={"trace_id": req.trace_id or ""},
                    )
                yield event.model_dump_json(exclude_none=True) + "\n"
        finally:
            cancel_registry.unregister(req.session_id)
            usage = done.get("usage") or {}
            logger.info(
                chat_msg(
                    "14.完成",
                    f"sessionId={req.session_id} outcome={outcome} "
                    f"intent={done.get('intent') or '-'} "
                    f"durationMs={int((time.perf_counter() - started) * 1000)} "
                    f"ttfbMs={ttfb_ms} tokenEvents={token_n} answerChars={answer_chars} "
                    f"citations={len(done.get('citations') or [])} "
                    f"toolCalls={len(done.get('toolCalls') or [])} "
                    f"tokens={usage.get('promptTokens', 0)}+{usage.get('completionTokens', 0)}",
                ),
                extra={"trace_id": req.trace_id or "", "event": "chat.stream.end"},
            )

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/cancel")
async def chat_cancel(body: CancelRequest, _: ServiceTokenDep) -> dict[str, bool]:
    """客户端断开 SSE 时由 Java 回调，打断进行中的 Mock/LLM 循环。"""
    logger.info(
        chat_msg("15.取消", f"sessionId={body.session_id}"),
        extra={"trace_id": getattr(body, "trace_id", None) or ""},
    )
    cancel_registry.cancel(body.session_id)
    return {"ok": True}

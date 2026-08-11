"""内部聊天流式路由（Java → Python）。"""

import logging
from collections.abc import AsyncIterator

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

    CHAT_BACKEND=orchestrator（默认）走 LangGraph；=mock 回退 Phase 2 Mock（排障用）。
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
        token_n = 0
        try:
            if settings.chat_backend == "mock":
                stream = mock_stream(req, cancel_event)
            else:
                stream = run_diagnosis_stream(req, cancel_event)
            async for event in stream:
                if event.type == "token":
                    token_n += 1
                    if token_n == 1 or token_n % 20 == 0:
                        logger.info(
                            chat_msg(
                                "16.输出Token",
                                f"sessionId={req.session_id} n={token_n} "
                                f"chunk=\"{preview(event.text)}\"",
                            ),
                            extra={"trace_id": req.trace_id or ""},
                        )
                elif event.type == "citation":
                    logger.info(
                        chat_msg(
                            "16.输出引用",
                            f"sessionId={req.session_id} data={preview(str(event.data))}",
                        ),
                        extra={"trace_id": req.trace_id or ""},
                    )
                elif event.type in ("done", "error"):
                    logger.info(
                        chat_msg(
                            "16.输出事件",
                            f"sessionId={req.session_id} type={event.type} "
                            f"payload={preview(event.model_dump_json(exclude_none=True))}",
                        ),
                        extra={"trace_id": req.trace_id or ""},
                    )
                yield event.model_dump_json(exclude_none=True) + "\n"
        finally:
            cancel_registry.unregister(req.session_id)
            logger.info(
                chat_msg(
                    "17.流关闭",
                    f"sessionId={req.session_id} tokenEvents={token_n}",
                ),
                extra={"trace_id": req.trace_id or ""},
            )

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/cancel")
async def chat_cancel(body: CancelRequest, _: ServiceTokenDep) -> dict[str, bool]:
    """客户端断开 SSE 时由 Java 回调，打断进行中的 Mock/LLM 循环。"""
    logger.info(
        chat_msg("18.取消", f"sessionId={body.session_id}"),
        extra={"trace_id": getattr(body, "trace_id", None) or ""},
    )
    cancel_registry.cancel(body.session_id)
    return {"ok": True}

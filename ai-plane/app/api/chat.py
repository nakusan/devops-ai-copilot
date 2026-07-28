"""内部聊天流式路由（Java → Python）。"""

from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import ServiceTokenDep
from app.graph.models.internal_chat_request import CancelRequest, InternalChatRequest
from app.graph.streaming.cancel_registry import cancel_registry
from app.graph.streaming.mock_streamer import mock_stream

router = APIRouter(prefix="/internal/v1/chat", tags=["internal-chat"])


@router.post("/stream")
async def chat_stream(
    req: InternalChatRequest,
    _: ServiceTokenDep,
) -> StreamingResponse:
    """返回 application/x-ndjson：每行一个 StreamEvent JSON。

    为何不用 SSE 对内：Java WebClient 按行解析 NDJSON 更简单，且与对外 SSE 职责分离（P8）。
    """

    cancel_event = cancel_registry.register(req.session_id)

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in mock_stream(req, cancel_event):
                # exclude_none：避免无用字段污染协议
                yield event.model_dump_json(exclude_none=True) + "\n"
        finally:
            cancel_registry.unregister(req.session_id)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/cancel")
async def chat_cancel(body: CancelRequest, _: ServiceTokenDep) -> dict[str, bool]:
    """客户端断开 SSE 时由 Java 回调，打断进行中的 Mock/LLM 循环。"""
    cancel_registry.cancel(body.session_id)
    return {"ok": True}

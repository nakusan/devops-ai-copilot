"""流式事件辅助 — state → citation / done 载荷。"""

from typing import Any

from app.graph.models.stream_event import StreamEvent


def citation_event(citations: list[dict[str, Any]]) -> StreamEvent:
    """检索完成后单独发 citation 行，Java 转 SSE event:citation。"""
    return StreamEvent(type="citation", data={"citations": citations})


def build_done_payload(
    *,
    intent: str,
    model: str,
    latency_ms: int,
    usage: dict[str, Any],
    citations: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    """对齐 Java ChatService metadata_json 写入格式。"""
    return {
        "intent": intent,
        "model": model,
        "latencyMs": latency_ms,
        "usage": usage,
        "citations": citations,
        "toolCalls": tool_calls,
    }

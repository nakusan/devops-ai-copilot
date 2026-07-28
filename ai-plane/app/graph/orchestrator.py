"""诊断编排器 — 模式 A：graph.ainvoke → citation → LLM stream → done。"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator

from app.graph.builder import get_diagnosis_graph
from app.graph.llm.llm_client import pop_stream_usage, stream_chat
from app.graph.models.internal_chat_request import InternalChatRequest
from app.graph.models.stream_event import StreamEvent, done_event, error_event
from app.graph.state import DiagnosisState, init_state_from_request
from app.graph.streaming.event_emitter import build_done_payload, citation_event

logger = logging.getLogger(__name__)


async def run_diagnosis_stream(
    req: InternalChatRequest,
    cancel_event: asyncio.Event,
) -> AsyncIterator[StreamEvent]:
    """替换 mock_stream 的主入口。"""
    started = time.perf_counter()
    state: DiagnosisState = init_state_from_request(req)

    try:
        graph = get_diagnosis_graph()
        state = await graph.ainvoke(state)  # type: ignore[assignment]

        intent = state.get("intent") or "direct"
        logger.info(
            "diagnosis graph done trace_id=%s session_id=%s intent=%s",
            req.trace_id,
            req.session_id,
            intent,
        )

        citations = state.get("citations") or []
        if citations:
            yield citation_event(citations)

        if cancel_event.is_set():
            yield error_event("CANCELLED", "生成已取消")
            return

        cfg = req.agent_config
        messages = state.get("llm_messages") or []
        had_error = False

        async for evt in stream_chat(
            messages,
            model=cfg.model,
            temperature=cfg.temperature,
            cancel_event=cancel_event,
            timeout_seconds=cfg.llm_timeout_seconds,
            user_message=req.user_message,
        ):
            if evt.type == "error":
                had_error = True
            yield evt

        if had_error or cancel_event.is_set():
            return

        usage = pop_stream_usage()
        if not usage:
            usage = {"promptTokens": 0, "completionTokens": 0, "totalTokens": 0}

        latency_ms = int((time.perf_counter() - started) * 1000)
        tool_calls = state.get("tool_calls") or []
        yield done_event(
            build_done_payload(
                intent=intent,
                model=cfg.model,
                latency_ms=latency_ms,
                usage=usage,
                citations=citations,
                tool_calls=tool_calls,
            )
        )
    except asyncio.CancelledError:
        yield error_event("CANCELLED", "生成已取消")
    except Exception as ex:  # noqa: BLE001
        logger.exception(
            "diagnosis failed trace_id=%s session_id=%s",
            req.trace_id,
            req.session_id,
        )
        yield error_event("AGENT_ERROR", str(ex))

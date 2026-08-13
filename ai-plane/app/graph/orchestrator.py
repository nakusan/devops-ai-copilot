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
from app.observability.logging import chat_msg, preview
from app.observability.metrics import CHAT_STREAM_DURATION, observe_with_exemplar
from app.observability.otel import get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer("ai-plane.orchestrator")


async def run_diagnosis_stream(
    req: InternalChatRequest,
    cancel_event: asyncio.Event,
) -> AsyncIterator[StreamEvent]:
    """替换 mock_stream 的主入口。"""
    started = time.perf_counter()
    state: DiagnosisState = init_state_from_request(req)

    with _tracer.start_as_current_span("internal.chat") as span:
        span.set_attribute("session.id", req.session_id)
        if req.trace_id:
            span.set_attribute("copilot.trace_id", req.trace_id)
        try:
            logger.info(
                chat_msg(
                    "11.图开始",
                    f"sessionId={req.session_id} "
                    f"user=\"{preview(req.user_message)}\"",
                ),
                extra={"trace_id": req.trace_id or "", "event": "chat.stream.graph_start"},
            )
            graph = get_diagnosis_graph()
            state = await graph.ainvoke(state)  # type: ignore[assignment]

            intent = state.get("intent") or "direct"
            citations = state.get("citations") or []
            chunks = state.get("retrieved_chunks") or []
            tool_calls = state.get("tool_calls") or []
            analysis_summary = state.get("analysis_summary")
            llm_messages = state.get("llm_messages") or []
            span.set_attribute("intent", intent)

            analysis_preview = preview(str(analysis_summary) if analysis_summary else "")
            logger.info(
                chat_msg(
                    "12.图完成",
                    f"sessionId={req.session_id} intent={intent} "
                    f"citations={len(citations)} chunks={len(chunks)} "
                    f"toolCalls={len(tool_calls)} "
                    f"hasAnalysis={bool(analysis_summary)} "
                    f"llmMessages={len(llm_messages)} "
                    f"analysisPreview=\"{analysis_preview}\"",
                ),
                extra={"trace_id": req.trace_id or "", "event": "chat.stream.graph_done"},
            )

            if citations:
                yield citation_event(citations)

            if cancel_event.is_set():
                yield error_event("CANCELLED", "生成已取消")
                return

            cfg = req.agent_config
            messages = llm_messages
            had_error = False

            logger.info(
                chat_msg(
                    "13.LLM开始",
                    f"sessionId={req.session_id} model={cfg.model} "
                    f"temp={cfg.temperature} msgCount={len(messages)}",
                ),
                extra={"trace_id": req.trace_id or ""},
            )

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
            logger.info(
                chat_msg(
                    "15.完成",
                    f"sessionId={req.session_id} durationMs={latency_ms} "
                    f"intent={intent} usage={usage}",
                ),
                extra={"trace_id": req.trace_id or "", "event": "chat.stream.end"},
            )
        except asyncio.CancelledError:
            yield error_event("CANCELLED", "生成已取消")
        except Exception as ex:  # noqa: BLE001
            logger.exception(
                chat_msg(
                    "15.错误",
                    f"sessionId={req.session_id} error=\"{preview(str(ex))}\"",
                ),
                extra={"trace_id": req.trace_id or ""},
            )
            yield error_event("AGENT_ERROR", str(ex))
        finally:
            observe_with_exemplar(CHAT_STREAM_DURATION, time.perf_counter() - started)

"""诊断编排器 — ReAct：规划轮(tools) → 执行工具 → 最终流式回答。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from app.config import settings
from app.graph.llm.llm_client import (
    complete_with_tools,
    merge_usage,
    pop_stream_usage,
    stream_chat,
    stream_text_chunks,
)
from app.graph.llm.prompt_builder import build_agent_messages
from app.graph.models.internal_chat_request import InternalChatRequest
from app.graph.models.stream_event import StreamEvent, done_event, error_event, tool_event
from app.graph.streaming.event_emitter import build_done_payload, citation_event
from app.graph.tools.executor import ToolExecution, execute_tool_calls
from app.graph.tools.registry import build_openai_tools, derive_intent
from app.observability.logging import chat_msg, preview
from app.observability.metrics import CHAT_STREAM_DURATION, observe_with_exemplar
from app.observability.otel import get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer("ai-plane.orchestrator")


async def run_diagnosis_stream(
    req: InternalChatRequest,
    cancel_event: asyncio.Event,
) -> AsyncIterator[StreamEvent]:
    """主入口：LLM function calling 循环 + 最终 token 流。"""
    started = time.perf_counter()
    cfg = req.agent_config
    agent_config = {
        "model": cfg.model,
        "system_prompt": cfg.system_prompt,
        "enable_rag": cfg.enable_rag,
        "enable_mcp": cfg.enable_mcp,
        "rag_top_k": cfg.rag_top_k,
        "rag_score_threshold": cfg.rag_score_threshold,
        "temperature": cfg.temperature,
        "max_history_messages": cfg.max_history_messages,
        "mcp_servers": cfg.mcp_servers,
        "llm_timeout_seconds": cfg.llm_timeout_seconds,
    }
    user_context = {
        "user_id": req.user_context.user_id,
        "team_id": req.user_context.team_id,
    }
    history = [{"role": m.role, "content": m.content} for m in req.history]
    messages: list[dict[str, Any]] = build_agent_messages(
        system_prompt=cfg.system_prompt,
        history=history,
        user_message=req.user_message,
    )
    tools = build_openai_tools(agent_config)
    max_rounds = max(1, settings.agent_max_tool_rounds)

    citations: list[dict[str, Any]] = []
    tool_call_records: list[dict[str, Any]] = []
    used_tools: set[str] = set()
    plan_rounds = 0
    usage_total: dict[str, Any] = {
        "promptTokens": 0,
        "completionTokens": 0,
        "totalTokens": 0,
    }

    with _tracer.start_as_current_span("internal.chat") as span:
        span.set_attribute("session.id", req.session_id)
        if req.trace_id:
            span.set_attribute("copilot.trace_id", req.trace_id)
        span.set_attribute("agent.tools", len(tools))
        trace_extra = {"trace_id": req.trace_id or ""}
        try:
            logger.info(
                chat_msg(
                    "11.编排",
                    f"sessionId={req.session_id} tools={len(tools)} "
                    f"maxRounds={max_rounds} model={cfg.model}",
                ),
                extra=trace_extra,
            )
            # 无可用工具：直接最终流式
            if not tools:
                async for evt in _final_stream(
                    messages,
                    req=req,
                    cancel_event=cancel_event,
                    prefetched_content=None,
                    prefetched_usage=None,
                    trace_id=req.trace_id,
                ):
                    if evt.type == "error":
                        yield evt
                        return
                    yield evt
                usage_total = merge_usage(usage_total, pop_stream_usage())
                yield _done(
                    req,
                    started,
                    intent="direct",
                    usage=usage_total,
                    citations=citations,
                    tool_calls=tool_call_records,
                )
                return

            for round_idx in range(max_rounds):
                if cancel_event.is_set():
                    yield error_event("CANCELLED", "生成已取消")
                    return

                offer_tools = tools if round_idx < max_rounds else None
                # 最后一轮仍可能带 tools；若模型继续要工具，下面会强制收束
                turn = await complete_with_tools(
                    messages,
                    model=cfg.model,
                    temperature=cfg.temperature,
                    cancel_event=cancel_event,
                    tools=offer_tools,
                    timeout_seconds=cfg.llm_timeout_seconds,
                )
                plan_rounds += 1
                usage_total = merge_usage(usage_total, turn.usage)

                if turn.cancelled or cancel_event.is_set():
                    yield error_event("CANCELLED", "生成已取消")
                    return
                if turn.error_event is not None:
                    yield turn.error_event
                    return

                if turn.tool_calls:
                    tool_names = ",".join(tc["name"] for tc in turn.tool_calls)
                    logger.info(
                        chat_msg(
                            "11.规划",
                            f"round={round_idx + 1} decision=tools tools={tool_names}",
                        ),
                        extra=trace_extra,
                    )
                    if round_idx >= max_rounds - 1:
                        # 工具轮次耗尽：丢掉本轮 tool_calls，强制最终生成
                        logger.warning(
                            chat_msg(
                                "11.规划",
                                f"round={round_idx + 1} decision=force_answer "
                                f"reason=max_rounds_exceeded maxRounds={max_rounds}",
                            ),
                            extra=trace_extra,
                        )
                        async for evt in _final_stream(
                            messages,
                            req=req,
                            cancel_event=cancel_event,
                            prefetched_content=None,
                            prefetched_usage=None,
                            trace_id=req.trace_id,
                        ):
                            if evt.type == "error":
                                yield evt
                                return
                            yield evt
                        usage_total = merge_usage(usage_total, pop_stream_usage())
                        break

                    assistant_tc = {
                        "role": "assistant",
                        "content": turn.content or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": _args_json(tc.get("arguments")),
                                },
                            }
                            for tc in turn.tool_calls
                        ],
                    }
                    messages.append(assistant_tc)

                    if cancel_event.is_set():
                        yield error_event("CANCELLED", "生成已取消")
                        return

                    for tc in turn.tool_calls:
                        yield tool_event(
                            tc["name"],
                            "start",
                            arguments=tc.get("arguments") or {},
                        )

                    executions = await execute_tool_calls(
                        turn.tool_calls,
                        agent_config=agent_config,
                        user_context=user_context,
                        trace_id=req.trace_id,
                    )
                    logger.info(
                        chat_msg(
                            "12.执行",
                            f"round={round_idx + 1} "
                            f"results={_format_tool_results(executions)}",
                        ),
                        extra=trace_extra,
                    )

                    new_citations: list[dict[str, Any]] = []
                    for ex in executions:
                        used_tools.add(ex.name)
                        tool_call_records.append(ex.tool_call_record)
                        if ex.citations:
                            new_citations.extend(ex.citations)
                        yield tool_event(
                            ex.name,
                            "done",
                            arguments=ex.arguments,
                            success=ex.success,
                            error=ex.error,
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": ex.tool_call_id,
                                "content": ex.content,
                            }
                        )

                    if new_citations:
                        # 去重：按 chunkId
                        seen = {c.get("chunkId") for c in citations}
                        for c in new_citations:
                            cid = c.get("chunkId")
                            if cid not in seen:
                                citations.append(c)
                                seen.add(cid)
                        yield citation_event(citations)
                    continue

                # 无 tool_calls：最终回答（优先切片已有 content，避免再打模型）
                answer_chars = len(turn.content or "")
                logger.info(
                    chat_msg(
                        "11.规划",
                        f"round={round_idx + 1} decision=answer contentChars={answer_chars}",
                    ),
                    extra=trace_extra,
                )
                async for evt in _final_stream(
                    messages,
                    req=req,
                    cancel_event=cancel_event,
                    prefetched_content=turn.content,
                    prefetched_usage=turn.usage,
                    trace_id=req.trace_id,
                ):
                    if evt.type == "error":
                        yield evt
                        return
                    yield evt
                # prefetched 路径 usage 已在 turn 计入；stream 路径再 pop
                if not (turn.content and turn.content.strip()):
                    usage_total = merge_usage(usage_total, pop_stream_usage())
                break
            else:
                # for 正常结束且未 break：不应到达；保险
                pass

            intent = derive_intent(used_tools)
            span.set_attribute("intent", intent)
            span.set_attribute("agent.plan_rounds", plan_rounds)
            yield _done(
                req,
                started,
                intent=intent,
                usage=usage_total,
                citations=citations,
                tool_calls=tool_call_records,
            )
        except asyncio.CancelledError:
            yield error_event("CANCELLED", "生成已取消")
        except Exception as ex:  # noqa: BLE001
            logger.exception(
                chat_msg(
                    "14.异常",
                    f"sessionId={req.session_id} error=\"{preview(str(ex))}\"",
                ),
                extra={"trace_id": req.trace_id or ""},
            )
            yield error_event("AGENT_ERROR", str(ex))
        finally:
            observe_with_exemplar(CHAT_STREAM_DURATION, time.perf_counter() - started)


async def _final_stream(
    messages: list[dict[str, Any]],
    *,
    req: InternalChatRequest,
    cancel_event: asyncio.Event,
    prefetched_content: str | None,
    prefetched_usage: dict[str, Any] | None,
    trace_id: str | None = None,
) -> AsyncIterator[StreamEvent]:
    """最终回答：有预取 content 则本地切片；否则无 tools 流式生成。"""
    cfg = req.agent_config
    mode = "prefetch" if prefetched_content and prefetched_content.strip() else "stream"
    logger.info(
        chat_msg("13.生成", f"mode={mode} answerChars={len(prefetched_content or '')}"),
        extra={"trace_id": trace_id or ""},
    )
    if prefetched_content and prefetched_content.strip():
        async for evt in stream_text_chunks(
            prefetched_content,
            cancel_event=cancel_event,
            usage=prefetched_usage,
        ):
            yield evt
        return
    async for evt in stream_chat(
        messages,
        model=cfg.model,
        temperature=cfg.temperature,
        cancel_event=cancel_event,
        timeout_seconds=cfg.llm_timeout_seconds,
        user_message=req.user_message,
    ):
        yield evt


def _done(
    req: InternalChatRequest,
    started: float,
    *,
    intent: str,
    usage: dict[str, Any],
    citations: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
) -> StreamEvent:
    latency_ms = int((time.perf_counter() - started) * 1000)
    if not usage:
        usage = {"promptTokens": 0, "completionTokens": 0, "totalTokens": 0}
    return done_event(
        build_done_payload(
            intent=intent,
            model=req.agent_config.model,
            latency_ms=latency_ms,
            usage=usage,
            citations=citations,
            tool_calls=tool_calls,
        )
    )


def _format_tool_results(executions: list[ToolExecution]) -> str:
    """紧凑汇总：retrieve 带 hits，其余 ok/err。"""
    parts: list[str] = []
    for ex in executions:
        if ex.name == "retrieve_knowledge" and ex.success:
            hits = (ex.tool_call_record.get("result") or {}).get("hits", 0)
            parts.append(f"{ex.name}:{hits}hits")
        elif ex.name in {"list_analysis_jobs", "get_analysis_job"} and ex.success:
            result = ex.tool_call_record.get("result") or {}
            if ex.name == "list_analysis_jobs":
                parts.append(f"{ex.name}:{result.get('count', 0)}")
            else:
                parts.append(f"{ex.name}:{result.get('jobId', '-')}")
        elif ex.success:
            parts.append(f"{ex.name}:ok")
        else:
            parts.append(f"{ex.name}:err")
    return ",".join(parts) if parts else "-"


def _args_json(arguments: Any) -> str:
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments or {}, ensure_ascii=False)

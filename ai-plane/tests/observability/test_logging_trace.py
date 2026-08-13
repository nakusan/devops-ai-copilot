"""Observability P1：日志 traceId 优先级 + async generator span 行为（设计 6.10 §5.4 / §9 R1）。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.observability.logging import ReadableFormatter, _resolve_trace


def _local_tracer(name: str = "test") -> tuple[TracerProvider, trace.Tracer]:
    """使用独立 TracerProvider，避免全局 set_tracer_provider 不可覆盖。"""
    provider = TracerProvider()
    return provider, provider.get_tracer(name)


def test_resolve_trace_prefers_otel_span_over_extra() -> None:
    """有活跃 span 时，日志必须用 OTel traceId，不被 extra 覆盖（修 B5）。"""
    _provider, tracer = _local_tracer("test.logging")

    with tracer.start_as_current_span("parent"):
        span = trace.get_current_span()
        ctx = span.get_span_context()
        assert ctx is not None and ctx.is_valid
        otel_trace = format(ctx.trace_id, "032x")

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.trace_id = "business-trace-id-should-not-win"
        record.span_id = "ffffffffffffffff"

        resolved_trace, resolved_span = _resolve_trace(record)
        assert resolved_trace == otel_trace
        assert resolved_span == format(ctx.span_id, "016x")
        assert "business" not in resolved_trace


def test_resolve_trace_falls_back_to_extra_without_span() -> None:
    """无活跃 span 时，允许用 extra 兜底（Kafka 消费入口等）。"""
    from opentelemetry.context import attach, detach

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.trace_id = "abcd1234efgh5678"
    record.span_id = "0011223344556677"

    # 脱离可能残留的 current span，确保走 extra 兜底
    token = attach(trace.set_span_in_context(trace.INVALID_SPAN))
    try:
        resolved_trace, resolved_span = _resolve_trace(record)
    finally:
        detach(token)

    assert resolved_trace == "abcd1234efgh5678"
    assert resolved_span == "0011223344556677"


def test_readable_formatter_uses_otel_trace_prefix() -> None:
    _provider, tracer = _local_tracer("test.logging")
    fmt = ReadableFormatter()

    with tracer.start_as_current_span("chat"):
        span = trace.get_current_span()
        ctx = span.get_span_context()
        assert ctx is not None
        expected = format(ctx.trace_id, "032x")[:16]

        record = logging.LogRecord(
            name="app.api.chat",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="[CHAT] step=10.接收请求",
            args=(),
            exc_info=None,
        )
        record.trace_id = "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
        line = fmt.format(record)
        assert f"[traceId={expected}]" in line
        assert "zzzz" not in line


@pytest.mark.asyncio
async def test_r1_async_generator_span_parent_child() -> None:
    """P7-04 / §9 R1：async generator 内跨 yield 持有 span，子 span 父子关系应正确。

    结论（同任务内 aiter 消费）：父子关系正常、span 能结束。
    生产若出现 Failed to detach / 永不结束，再按方案 B 显式传 context。
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test.r1")

    async def stream_with_span() -> AsyncIterator[str]:
        with tracer.start_as_current_span("internal.chat") as parent:
            parent_id = parent.get_span_context().span_id
            with tracer.start_as_current_span("llm.completion") as child:
                assert child.get_span_context().span_id != parent_id
                yield "a"
                yield "b"
            current = trace.get_current_span()
            assert current.get_span_context().span_id == parent_id

    tokens: list[str] = []
    async for t in stream_with_span():
        tokens.append(t)

    assert tokens == ["a", "b"]
    spans = exporter.get_finished_spans()
    by_name = {s.name: s for s in spans}
    assert "internal.chat" in by_name
    assert "llm.completion" in by_name
    parent = by_name["internal.chat"]
    child = by_name["llm.completion"]
    assert child.parent is not None
    assert child.parent.span_id == parent.context.span_id
    assert parent.end_time is not None
    assert child.end_time is not None

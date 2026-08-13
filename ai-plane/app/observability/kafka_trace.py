"""Kafka consumer 侧 W3C 上下文提取（设计 6.10 §7.1）。

header 是链路真相；消息体 traceId 仅作日志便利。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry.propagate import extract
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

from app.observability.otel import get_tracer

_tracer = get_tracer("ai-plane.kafka")


def kafka_header_carrier(msg: Any) -> dict[str, str]:
    """aiokafka headers: list[tuple[str, bytes | None]] → OTel TextMap carrier。"""
    carrier: dict[str, str] = {}
    for item in msg.headers or ():
        if not item:
            continue
        key, value = item[0], item[1] if len(item) > 1 else None
        if value is None:
            continue
        if isinstance(value, (bytes, bytearray)):
            carrier[str(key)] = value.decode("utf-8", errors="replace")
        else:
            carrier[str(key)] = str(value)
    return carrier


@contextmanager
def kafka_consumer_span(msg: Any) -> Iterator[Span]:
    """从 record header extract 并创建 CONSUMER span。"""
    ctx = extract(kafka_header_carrier(msg))
    with _tracer.start_as_current_span(
        f"{msg.topic} receive",
        context=ctx,
        kind=SpanKind.CONSUMER,
    ) as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination.name", msg.topic)
        if msg.partition is not None:
            span.set_attribute("messaging.kafka.partition", msg.partition)
        if msg.offset is not None:
            span.set_attribute("messaging.kafka.offset", msg.offset)
        yield span


def mark_dlq(span: Span) -> None:
    span.set_status(Status(StatusCode.ERROR, "sent to DLQ"))

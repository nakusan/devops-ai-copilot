"""OpenTelemetry Tracer 初始化（设计 6.7 §3.4.2）。

MVP：无 OTLP endpoint 时用 LoggingSpanExporter，保证仍有 spanId 可供日志关联；
配置了 OTEL_EXPORTER_OTLP_ENDPOINT 则导出到 Collector（V1）。
"""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

logger = logging.getLogger(__name__)

_initialized = False


def setup_otel(*, service_name: str, otlp_endpoint: str | None = None) -> None:
    """进程级初始化 TracerProvider；幂等。"""
    global _initialized
    if _initialized:
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("otel OTLP exporter enabled endpoint=%s", otlp_endpoint)
        except Exception:  # noqa: BLE001
            logger.exception("otel OTLP exporter init failed, falling back to console")
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    else:
        # MVP：无 Collector 时不刷屏；仍初始化 Tracer，供手工 span + 日志取 trace/span id
        logger.info("otel initialized without OTLP (spans for in-process correlation only)")

    trace.set_tracer_provider(provider)
    _initialized = True


def get_tracer(name: str = "ai-plane") -> trace.Tracer:
    return trace.get_tracer(name)


def instrument_fastapi(app: object) -> None:
    """FastAPI 自动 http.server span；失败时降级（不阻塞启动）。"""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        logger.warning("FastAPI OTel instrumentation skipped", exc_info=True)


def instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:  # noqa: BLE001
        logger.warning("httpx OTel instrumentation skipped", exc_info=True)

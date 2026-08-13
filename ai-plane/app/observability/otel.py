"""OpenTelemetry Tracer 初始化（设计 6.7 §3.4.2 / 6.10 §5.2）。

无 OTLP endpoint 时仅初始化 Tracer（供手工 span + 日志取 trace/span id）；
配置了 OTEL_EXPORTER_OTLP_ENDPOINT 则 Batch 导出到 Tempo（直连，无 Collector）。
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
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased, TraceIdRatioBased

from app.config import settings

logger = logging.getLogger(__name__)

_initialized = False
_provider: TracerProvider | None = None


def setup_otel(*, service_name: str, otlp_endpoint: str | None = None) -> None:
    """进程级初始化 TracerProvider；幂等。"""
    global _initialized, _provider
    if _initialized:
        return

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": settings.service_version,
            "deployment.environment": settings.deploy_env,
        }
    )
    # 低流量全采样；Java 侧采样决策通过 ParentBased 被尊重（设计 6.10 §9 R6）
    sample_rate = settings.otel_sample_rate
    root_sampler = ALWAYS_ON if sample_rate >= 1.0 else TraceIdRatioBased(sample_rate)
    sampler = ParentBased(root=root_sampler)
    provider = TracerProvider(resource=resource, sampler=sampler)

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
        # 无 Tempo 时不刷屏；仍初始化 Tracer，供手工 span + 日志取 trace/span id
        logger.info("otel initialized without OTLP (spans for in-process correlation only)")

    trace.set_tracer_provider(provider)
    _provider = provider
    _initialized = True


def shutdown_otel() -> None:
    """进程退出前 flush BatchSpanProcessor（设计 6.10 §5.3 / F3）。"""
    global _provider
    if _provider is None:
        return
    try:
        _provider.shutdown()
        logger.info("otel TracerProvider shutdown complete")
    except Exception:  # noqa: BLE001
        logger.exception("otel TracerProvider shutdown failed")
    finally:
        _provider = None


def get_tracer(name: str = "ai-plane") -> trace.Tracer:
    return trace.get_tracer(name)


def instrument_fastapi(app: object) -> None:
    """FastAPI 自动 http.server span；失败时降级（不阻塞启动）。

    排除 ASGI send/receive 子 span：流式 NDJSON 每个 yield 都会触发一次
    ``http send``，会淹没业务 span（设计 6.10 / 流式噪音）。
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,  # type: ignore[arg-type]
            exclude_spans=["send", "receive"],
        )
    except Exception:  # noqa: BLE001
        logger.warning("FastAPI OTel instrumentation skipped", exc_info=True)


def instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:  # noqa: BLE001
        logger.warning("httpx OTel instrumentation skipped", exc_info=True)


def instrument_asyncpg() -> None:
    """asyncpg 查询自动建 span（设计 6.10 §7.2）；失败时降级。"""
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
    except Exception:  # noqa: BLE001
        logger.warning("asyncpg OTel instrumentation skipped", exc_info=True)

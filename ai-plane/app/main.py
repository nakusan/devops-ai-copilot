"""FastAPI 应用入口（仅 HTTP / 聊天编排；Kafka 消费见 app.worker）。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.config import settings
from app.observability import (
    configure_logging,
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    setup_otel,
    shutdown_otel,
)
from app.observability.middleware import ObservabilityMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Kafka Consumer 已拆到独立进程：`python -m app.worker`
    # 避免重活与聊天 SSE 争抢同一事件循环。
    try:
        yield
    finally:
        shutdown_otel()


configure_logging(service_name=settings.otel_service_name)
setup_otel(
    service_name=settings.otel_service_name,
    otlp_endpoint=settings.otel_exporter_otlp_endpoint,
)
instrument_httpx()
instrument_asyncpg()

app = FastAPI(
    title="DevOps AI Copilot — AI Plane",
    version="0.1.0",
    lifespan=lifespan,
)
# Observability 先挂，再 instrument：FastAPIInstrumentor 成为最外层，
# 中间件内才能拿到 server span 挂 copilot.trace_id（设计 6.10 §7.3）。
app.add_middleware(ObservabilityMiddleware)
instrument_fastapi(app)
app.include_router(api_router)

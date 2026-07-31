"""FastAPI 应用入口（仅 HTTP / 聊天编排；Kafka 消费见 app.worker）。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Kafka Consumer 已拆到独立进程：`python -m app.worker`
    # 避免重活与聊天 SSE 争抢同一事件循环。
    yield


app = FastAPI(
    title="DevOps AI Copilot — AI Plane",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(api_router)

"""FastAPI 应用入口（Phase 0 骨架）。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # 后续周次再挂载 Kafka 消费者 / MCP / LLM 客户端。
    yield


app = FastAPI(
    title="DevOps AI Copilot — AI Plane",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(api_router)

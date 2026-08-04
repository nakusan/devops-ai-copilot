"""智能面 HTTP 路由聚合。"""

from fastapi import APIRouter

from app.api import chat, health, metrics

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(metrics.router)
api_router.include_router(chat.router)

"""Prometheus /metrics 端点。"""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus scrape 入口（设计 6.7 §3.4.3）。"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

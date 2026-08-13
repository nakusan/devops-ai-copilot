"""Prometheus /metrics 端点（支持 OpenMetrics exemplars，设计 6.10 §8.2）。"""

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from prometheus_client.openmetrics.exposition import (
    CONTENT_TYPE_LATEST as OM_CONTENT_TYPE_LATEST,
)
from prometheus_client.openmetrics.exposition import generate_latest as om_generate_latest

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    """Prometheus scrape 入口；Accept 含 openmetrics 时输出 exemplar。"""
    accept = request.headers.get("accept", "")
    if "application/openmetrics-text" in accept:
        return Response(
            content=om_generate_latest(REGISTRY),
            media_type=OM_CONTENT_TYPE_LATEST,
        )
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

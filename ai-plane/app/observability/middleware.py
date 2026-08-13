"""FastAPI 中间件：仅记 HTTP 指标 + 挂业务 trace 属性（设计 6.10 §7.3）。

span 创建与 W3C extract 交给 FastAPIInstrumentor，避免重复 server span（F1）。
path label 用路由模板，避免 UUID 高基数（F2）。
"""

from __future__ import annotations

from collections.abc import Callable

from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.observability.metrics import HTTP_REQUESTS


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """记录 http_requests_total；把 X-Trace-Id 挂到当前 server span。"""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # /metrics 自身不计入业务请求，避免 scrape 污染
        if request.url.path == "/metrics":
            return await call_next(request)

        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            # FastAPIInstrumentor 已建 server span；中间件须挂在其内侧（见 main.py 顺序）
            span = trace.get_current_span()
            x_trace = request.headers.get("x-trace-id")
            if x_trace and span is not None and span.is_recording():
                span.set_attribute("copilot.trace_id", x_trace)

            route = request.scope.get("route")
            path = getattr(route, "path", None) or request.url.path
            HTTP_REQUESTS.labels(
                method=request.method,
                path=path,
                status=str(status),
            ).inc()

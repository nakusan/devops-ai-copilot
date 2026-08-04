"""FastAPI 中间件：传播 trace 上下文 + 基础 HTTP 计数。"""

from __future__ import annotations

import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.observability.metrics import HTTP_REQUESTS
from app.observability.otel import get_tracer


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """从入站 header 提取 W3C context，创建 internal span，并记录 http_requests_total。"""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._tracer = get_tracer("ai-plane.http")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # /metrics 自身不计入业务请求，避免 scrape 污染
        if request.url.path == "/metrics":
            return await call_next(request)

        from opentelemetry.propagate import extract

        ctx = extract(dict(request.headers))
        started = time.perf_counter()
        status = 500
        with self._tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            context=ctx,
        ) as span:
            # 业务契约字段：Java 也传 X-Trace-Id / body.traceId
            x_trace = request.headers.get("x-trace-id")
            if x_trace:
                span.set_attribute("copilot.trace_id", x_trace)
            try:
                response = await call_next(request)
                status = response.status_code
                return response
            finally:
                span.set_attribute("http.status_code", status)
                # 低基数 path：去掉 UUID 等动态段会更好，MVP 先用原始 path
                path = request.url.path
                HTTP_REQUESTS.labels(
                    method=request.method,
                    path=path,
                    status=str(status),
                ).inc()
                _ = time.perf_counter() - started

"""结构化 JSON 日志 + traceId/spanId 注入（设计 6.7 §3.4.4）。"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


def _current_trace_context() -> tuple[str, str]:
    """从 OTel 当前 span 取 trace/span id；无活跃 span 时返回空串。"""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx is None or not ctx.is_valid:
            return "", ""
        return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except Exception:  # noqa: BLE001
        return "", ""


class JsonFormatter(logging.Formatter):
    """输出单行 JSON，字段与控制面 ErrorResponse / 设计书 schema 对齐。"""

    def __init__(self, service: str = "ai-plane") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = _current_trace_context()
        # LogRecord 标准类型无这些字段；业务经 logger.info(..., extra={...}) 注入
        # 走 __dict__ 同时满足 pyright（无属性）与 ruff（避免 B009）
        extra_trace = record.__dict__.get("trace_id")
        if extra_trace:
            trace_id = str(extra_trace)
        extra_span = record.__dict__.get("span_id")
        if extra_span:
            span_id = str(extra_span)

        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": self.service,
            "traceId": trace_id or None,
            "spanId": span_id or None,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event = record.__dict__.get("event")
        if event is not None:
            payload["event"] = event
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(*, service_name: str = "ai-plane", level: int = logging.INFO) -> None:
    """配置根 logger 为 JSON；幂等覆盖 handlers。"""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service=service_name))
    root.addHandler(handler)
    root.setLevel(level)

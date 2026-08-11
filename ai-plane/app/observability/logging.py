"""可读日志格式（默认）+ 可选 JSON；聊天链路统一 [CHAT] 前缀。

约定：`[CHAT] step=序号.中文步骤名 key=value ...`，文本字段用 preview 截断。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

try:
    _SHANGHAI = ZoneInfo("Asia/Shanghai")
except Exception:  # noqa: BLE001 — 精简镜像可能缺 tzdata
    from datetime import timedelta, timezone

    _SHANGHAI = timezone(timedelta(hours=8))


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


def _resolve_trace(record: logging.LogRecord) -> tuple[str, str]:
    trace_id, span_id = _current_trace_context()
    extra_trace = record.__dict__.get("trace_id")
    if extra_trace:
        trace_id = str(extra_trace)
    extra_span = record.__dict__.get("span_id")
    if extra_span:
        span_id = str(extra_span)
    return trace_id or "", span_id or ""


def preview(text: str | None, max_len: int = 120) -> str:
    if not text:
        return ""
    one = " ".join(str(text).split())
    if len(one) <= max_len:
        return one
    return one[:max_len] + "…"


def chat_msg(step: str, details: str) -> str:
    return f"[CHAT] step={step} {details}"


def ingest_msg(kind: str, step: str, details: str) -> str:
    """异步文件链路：kind=knowledge|analysis。"""
    return f"[INGEST] step={step} kind={kind} {details}"


class ReadableFormatter(logging.Formatter):
    """一行一条，东八区时间，方便 docker logs 肉眼看。"""

    def format(self, record: logging.LogRecord) -> str:
        trace_id, _span = _resolve_trace(record)
        ts = datetime.now(_SHANGHAI).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        short_logger = record.name
        if len(short_logger) > 28:
            short_logger = short_logger[-28:]
        tid = trace_id[:16] if trace_id else "-"
        msg = record.getMessage()
        line = f"{ts} {record.levelname:<5} [traceId={tid}] {short_logger} - {msg}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class JsonFormatter(logging.Formatter):
    """输出单行 JSON（生产 / LOG_FORMAT=json）。"""

    def __init__(self, service: str = "ai-plane") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = _resolve_trace(record)
        payload: dict[str, Any] = {
            "timestamp": datetime.now(_SHANGHAI).isoformat(),
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
    """配置根 logger；默认可读文本，LOG_FORMAT=json 时切 JSON。"""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    fmt = (os.getenv("LOG_FORMAT") or "text").strip().lower()
    if fmt == "json":
        handler.setFormatter(JsonFormatter(service=service_name))
    else:
        handler.setFormatter(ReadableFormatter())
    root.addHandler(handler)
    root.setLevel(level)

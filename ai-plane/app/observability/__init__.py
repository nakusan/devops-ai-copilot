"""可观测性包：OTel + Prometheus + JSON 日志。"""

from app.observability.logging import configure_logging
from app.observability.otel import (
    instrument_asyncpg,
    instrument_fastapi,
    instrument_httpx,
    setup_otel,
    shutdown_otel,
)

__all__ = [
    "configure_logging",
    "instrument_asyncpg",
    "instrument_fastapi",
    "instrument_httpx",
    "setup_otel",
    "shutdown_otel",
]

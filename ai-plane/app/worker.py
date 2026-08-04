"""独立 Kafka Worker 进程入口（与 FastAPI 聊天进程分离）。

为何独立进程：
- 入库 / 分析是 CPU·IO 重活，挂在 uvicorn 里会拖慢聊天 SSE
- 可单独扩缩容、重启，不影响在线对话
- 业界常见形态：API 服务 + 异步 Worker（如 Celery worker / ingest worker）

启动：
  uv run python -m app.worker
  # 或
  uv run ai-plane-worker

可选环境变量 WORKER_ROLES=knowledge,analysis（默认两者都启）。
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Callable, Coroutine
from typing import Any

from app.config import settings
from app.observability import configure_logging, setup_otel

configure_logging(service_name=f"{settings.otel_service_name}-worker")
setup_otel(
    service_name=f"{settings.otel_service_name}-worker",
    otlp_endpoint=settings.otel_exporter_otlp_endpoint,
)
logger = logging.getLogger("app.worker")


def _parse_roles() -> set[str]:
    """WORKER_ROLES=knowledge,analysis → frozenset；空则两者都开。"""
    raw = (settings.worker_roles or "knowledge,analysis").strip()
    roles = {r.strip().lower() for r in raw.split(",") if r.strip()}
    allowed = {"knowledge", "analysis"}
    unknown = roles - allowed
    if unknown:
        raise SystemExit(f"未知 WORKER_ROLES={unknown}，允许值: {sorted(allowed)}")
    return roles or allowed


async def _run() -> None:
    if not settings.kafka_bootstrap:
        raise SystemExit(
            "KAFKA_BOOTSTRAP 未配置，Worker 无法启动。"
            "请在环境变量或 .env 中设置，例如 KAFKA_BOOTSTRAP=localhost:9092"
        )

    roles = _parse_roles()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        logger.info("收到停止信号，正在优雅退出…")
        stop.set()

    # SIGTERM/SIGINT：容器编排与 Ctrl+C 统一走优雅退出
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Windows 等不支持 add_signal_handler 时忽略；仍可用 KeyboardInterrupt
            pass

    from app.consumers.analysis_ingest import run_analysis_ingest_consumer
    from app.consumers.knowledge_ingest import run_knowledge_ingest_consumer

    runners: list[tuple[str, Callable[..., Coroutine[Any, Any, None]]]] = []
    if "knowledge" in roles:
        runners.append(("knowledge-ingest", run_knowledge_ingest_consumer))
    if "analysis" in roles:
        runners.append(("analysis-ingest", run_analysis_ingest_consumer))

    tasks = [
        asyncio.create_task(fn(stop), name=name) for name, fn in runners
    ]
    logger.info(
        "worker started bootstrap=%s roles=%s tasks=%s",
        settings.kafka_bootstrap,
        sorted(roles),
        [t.get_name() for t in tasks],
    )

    # 任一 consumer 异常退出 → 拉停其它任务，便于编排器重启整进程
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    stop.set()
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

    for t in done:
        if t.cancelled():
            continue
        exc = t.exception()
        if exc is not None:
            logger.exception("worker task failed name=%s", t.get_name(), exc_info=exc)
            raise SystemExit(1) from exc

    logger.info("worker stopped cleanly")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

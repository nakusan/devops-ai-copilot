"""顶层入口：转发到 analysis consumer（由 app.worker 启动）。"""

from app.analysis.consumer.analysis_ingest_consumer import run_analysis_ingest_consumer

__all__ = ["run_analysis_ingest_consumer"]

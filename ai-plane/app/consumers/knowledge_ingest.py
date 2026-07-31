"""顶层入口：转发到 knowledge ingest consumer。"""

from app.rag.consumer.ingest_consumer import run_knowledge_ingest_consumer

__all__ = ["run_knowledge_ingest_consumer"]

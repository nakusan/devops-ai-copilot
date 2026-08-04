"""知识入库 handler：下载 → 解析 → 清洗 → 切块 → Embedding → Java 写 chunks。"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from app.clients.java_internal_client import java_internal_client
from app.config import settings
from app.observability.metrics import INGEST_DURATION, INGEST_FAILURES
from app.observability.otel import get_tracer
from app.rag.models.events import KnowledgeIngestEvent
from app.rag.pipeline.chunker import chunk_text
from app.rag.pipeline.cleaner import clean
from app.rag.pipeline.downloader import download_to_temp
from app.rag.pipeline.embedder import embed_chunks
from app.rag.pipeline.parser import parse_document

logger = logging.getLogger(__name__)
_tracer = get_tracer("ai-plane.ingest")


async def handle_knowledge_ingest(event: KnowledgeIngestEvent, *, retry_count: int = 0) -> None:
    job = await java_internal_client.get_ingest_job(event.job_id)
    status = job.get("status")
    if status == "COMPLETED":
        logger.info("knowledge skip duplicate job_id=%s", event.job_id)
        return

    await java_internal_client.patch_ingest_job(event.job_id, status="PROCESSING")
    tmp: Path | None = None
    started = time.perf_counter()
    with _tracer.start_as_current_span("ingest.process") as span:
        span.set_attribute("ingest.job_id", event.job_id)
        try:
            tmp = await asyncio.to_thread(download_to_temp, event.object_key)
            raw_text = await asyncio.to_thread(parse_document, tmp, event.mime_type)
            text = clean(raw_text)
            if not text.strip():
                raise ValueError("文档解析结果为空（可能是扫描版 PDF）")

            chunks = chunk_text(
                text,
                base_metadata={
                    "source_object_key": event.object_key,
                    "embedding_model_version": settings.embedding_model_version,
                },
            )
            payloads = await embed_chunks(chunks)

            # 一次提交全部 chunks：Java batch 接口内部是「先删后插」，
            # 若拆多次 HTTP 会只留下最后一批。
            await java_internal_client.post_chunks_batch(
                event.document_id, [p.to_api_dict() for p in payloads]
            )

            await java_internal_client.patch_ingest_job(event.job_id, status="COMPLETED")
            INGEST_DURATION.observe(time.perf_counter() - started)
            logger.info(
                "knowledge ingest completed job_id=%s document_id=%s chunks=%d",
                event.job_id,
                event.document_id,
                len(payloads),
            )
        except Exception as ex:
            INGEST_FAILURES.labels(reason=type(ex).__name__).inc()
            INGEST_DURATION.observe(time.perf_counter() - started)
            logger.exception("knowledge ingest failed job_id=%s", event.job_id)
            await java_internal_client.patch_ingest_job(
                event.job_id,
                status="FAILED",
                error_message=str(ex)[:500],
                retry_count=retry_count,
            )
            raise
        finally:
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass

"""知识入库 handler：下载 → 解析 → 清洗 → 切块 → Embedding → Java 写 chunks。"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path

from app.clients.java_internal_client import java_internal_client
from app.config import settings
from app.observability.logging import ingest_msg, preview
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
_KIND = "knowledge"


async def handle_knowledge_ingest(event: KnowledgeIngestEvent, *, retry_count: int = 0) -> None:
    trace = event.trace_id or ""
    job = await java_internal_client.get_ingest_job(event.job_id)
    status = job.get("status")
    if status == "COMPLETED":
        logger.info(
            ingest_msg(
                _KIND,
                "10.skip",
                f"jobId={event.job_id} documentId={event.document_id} reason=already_completed",
            ),
            extra={"trace_id": trace},
        )
        return

    logger.info(
        ingest_msg(
            _KIND,
            "11.process_start",
            f"jobId={event.job_id} documentId={event.document_id} "
            f"objectKey={event.object_key} mimeType={event.mime_type} "
            f"retry={retry_count} prevStatus={status}",
        ),
        extra={"trace_id": trace},
    )

    await java_internal_client.patch_ingest_job(event.job_id, status="PROCESSING")
    tmp: Path | None = None
    started = time.perf_counter()
    with _tracer.start_as_current_span("ingest.process") as span:
        span.set_attribute("ingest.job_id", str(event.job_id))
        try:
            tmp = await asyncio.to_thread(download_to_temp, event.object_key)
            logger.info(
                ingest_msg(
                    _KIND,
                    "12.download",
                    f"jobId={event.job_id} objectKey={event.object_key} tmp={tmp}",
                ),
                extra={"trace_id": trace},
            )

            raw_text = await asyncio.to_thread(parse_document, tmp, event.mime_type)
            text = clean(raw_text)
            if not text.strip():
                raise ValueError("文档解析结果为空（可能是扫描版 PDF）")

            logger.info(
                ingest_msg(
                    _KIND,
                    "13.parse",
                    f"jobId={event.job_id} rawChars={len(raw_text)} cleanChars={len(text)} "
                    f"preview=\"{preview(text)}\"",
                ),
                extra={"trace_id": trace},
            )

            chunks = chunk_text(
                text,
                base_metadata={
                    "source_object_key": event.object_key,
                    "embedding_model_version": settings.embedding_model_version,
                },
            )
            payloads = await embed_chunks(chunks)
            logger.info(
                ingest_msg(
                    _KIND,
                    "14.embed",
                    f"jobId={event.job_id} chunks={len(chunks)} vectors={len(payloads)}",
                ),
                extra={"trace_id": trace},
            )

            await java_internal_client.post_chunks_batch(
                event.document_id, [p.to_api_dict() for p in payloads]
            )

            await java_internal_client.patch_ingest_job(event.job_id, status="COMPLETED")
            duration_ms = int((time.perf_counter() - started) * 1000)
            INGEST_DURATION.observe(time.perf_counter() - started)
            logger.info(
                ingest_msg(
                    _KIND,
                    "17.end",
                    f"jobId={event.job_id} documentId={event.document_id} "
                    f"status=COMPLETED chunks={len(payloads)} durationMs={duration_ms}",
                ),
                extra={"trace_id": trace},
            )
        except Exception as ex:
            INGEST_FAILURES.labels(reason=type(ex).__name__).inc()
            INGEST_DURATION.observe(time.perf_counter() - started)
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                ingest_msg(
                    _KIND,
                    "17.end",
                    f"jobId={event.job_id} documentId={event.document_id} "
                    f"status=FAILED durationMs={duration_ms} error=\"{preview(str(ex))}\"",
                ),
                extra={"trace_id": trace},
            )
            await java_internal_client.patch_ingest_job(
                event.job_id,
                status="FAILED",
                error_message=str(ex)[:500],
                retry_count=retry_count,
            )
            raise
        finally:
            if tmp is not None:
                with contextlib.suppress(OSError):
                    tmp.unlink(missing_ok=True)

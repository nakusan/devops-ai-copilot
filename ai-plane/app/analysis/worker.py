"""Analysis Worker：消费 analysis.ingest.v1，简化解析并回调 Java。"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from pathlib import Path

from app.analysis.models.analysis_ingest_event import AnalysisIngestEvent
from app.analysis.parser.keyword_analyzer import analyze_text_sample, build_summary
from app.analysis.parser.text_sampler import sample_text
from app.clients import java_internal_client as _jic_mod
from app.clients import minio_client
from app.config import settings
from app.observability.logging import ingest_msg, preview

logger = logging.getLogger(__name__)
_KIND = "analysis"


async def handle_analysis_ingest(event: AnalysisIngestEvent, *, retry_count: int = 0) -> None:
    """处理单条分析事件（幂等：COMPLETED 跳过）。"""
    trace = event.trace_id or ""
    java = _jic_mod.java_internal_client
    job = await java.get_analysis_job(event.job_id)
    status = job.get("status")
    if status == "COMPLETED":
        logger.info(
            ingest_msg(
                _KIND,
                "10.skip",
                f"jobId={event.job_id} reason=already_completed",
            ),
            extra={"trace_id": trace},
        )
        return

    logger.info(
        ingest_msg(
            _KIND,
            "11.process_start",
            f"jobId={event.job_id} objectKey={event.object_key} "
            f"fileType={event.file_type} retry={retry_count} prevStatus={status}",
        ),
        extra={"trace_id": trace},
    )

    await java.patch_analysis_job(event.job_id, status="PROCESSING")
    tmp: Path | None = None
    started = time.perf_counter()
    try:
        tmp = await asyncio.to_thread(minio_client.download_to_temp, event.object_key)
        logger.info(
            ingest_msg(
                _KIND,
                "12.download",
                f"jobId={event.job_id} objectKey={event.object_key} tmp={tmp}",
            ),
            extra={"trace_id": trace},
        )

        text = await asyncio.to_thread(sample_text, tmp, settings.analysis_sample_bytes)
        logger.info(
            ingest_msg(
                _KIND,
                "13.sample",
                f"jobId={event.job_id} sampleChars={len(text)} preview=\"{preview(text)}\"",
            ),
            extra={"trace_id": trace},
        )

        parsed = analyze_text_sample(text, event.file_type)
        summary = build_summary(parsed)
        logger.info(
            ingest_msg(
                _KIND,
                "14.analyze",
                f"jobId={event.job_id} fileType={event.file_type} "
                f"summaryLen={len(summary)} summary=\"{preview(summary)}\"",
            ),
            extra={"trace_id": trace},
        )

        result_key = f"analysis/{event.job_id}/result.json"
        payload = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
        await asyncio.to_thread(minio_client.upload_bytes, result_key, payload)
        logger.info(
            ingest_msg(
                _KIND,
                "15.result_saved",
                f"jobId={event.job_id} resultKey={result_key} bytes={len(payload)}",
            ),
            extra={"trace_id": trace},
        )

        await java.patch_analysis_job(
            event.job_id,
            status="COMPLETED",
            result_summary=summary,
            result_object_key=result_key,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            ingest_msg(
                _KIND,
                "17.end",
                f"jobId={event.job_id} status=COMPLETED durationMs={duration_ms} "
                f"summary=\"{preview(summary)}\"",
            ),
            extra={"trace_id": trace},
        )
    except Exception as ex:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.exception(
            ingest_msg(
                _KIND,
                "17.end",
                f"jobId={event.job_id} status=FAILED durationMs={duration_ms} "
                f"error=\"{preview(str(ex))}\"",
            ),
            extra={"trace_id": trace},
        )
        await java.patch_analysis_job(
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

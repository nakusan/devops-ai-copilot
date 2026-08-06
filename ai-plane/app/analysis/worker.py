"""Analysis Worker：消费 analysis.ingest.v1，简化解析并回调 Java。"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path

from app.analysis.models.analysis_ingest_event import AnalysisIngestEvent
from app.analysis.parser.keyword_analyzer import analyze_text_sample, build_summary
from app.analysis.parser.text_sampler import sample_text
from app.clients import java_internal_client as _jic_mod
from app.clients import minio_client
from app.config import settings

logger = logging.getLogger(__name__)


async def handle_analysis_ingest(event: AnalysisIngestEvent, *, retry_count: int = 0) -> None:
    """处理单条分析事件（幂等：COMPLETED/PROCESSING 跳过）。"""
    java = _jic_mod.java_internal_client
    job = await java.get_analysis_job(event.job_id)
    status = job.get("status")
    # 仅跳过 COMPLETED：PROCESSING 允许崩溃恢复重入（至少一次投递）
    if status == "COMPLETED":
        logger.info("analysis skip duplicate job_id=%s status=%s", event.job_id, status)
        return

    await java.patch_analysis_job(event.job_id, status="PROCESSING")
    tmp: Path | None = None
    try:
        tmp = await asyncio.to_thread(minio_client.download_to_temp, event.object_key)
        text = await asyncio.to_thread(sample_text, tmp, settings.analysis_sample_bytes)
        parsed = analyze_text_sample(text, event.file_type)
        summary = build_summary(parsed)

        # 可选详情写 MinIO，摘要进 DB（≤2KB 由 Java 侧截断）
        result_key = f"analysis/{event.job_id}/result.json"
        payload = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
        await asyncio.to_thread(minio_client.upload_bytes, result_key, payload)

        await java.patch_analysis_job(
            event.job_id,
            status="COMPLETED",
            result_summary=summary,
            result_object_key=result_key,
        )
        logger.info(
            "analysis completed job_id=%s file_type=%s summary_len=%d",
            event.job_id,
            event.file_type,
            len(summary),
        )
    except Exception as ex:
        logger.exception("analysis failed job_id=%s", event.job_id)
        await java.patch_analysis_job(
            event.job_id,
            status="FAILED",
            error_message=str(ex)[:500],
            retry_count=retry_count,
        )
        raise
    finally:
        # 清理临时文件：忽略并发删除 / 权限等 OSError，避免掩盖业务异常
        if tmp is not None:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)

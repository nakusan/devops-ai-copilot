"""Kafka Consumer：analysis.ingest.v1。"""

from __future__ import annotations

import asyncio
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.analysis.models.analysis_ingest_event import AnalysisIngestEvent
from app.analysis.worker import handle_analysis_ingest
from app.config import settings
from app.observability.logging import ingest_msg

logger = logging.getLogger(__name__)
_KIND = "analysis"


async def run_analysis_ingest_consumer(stop_event: asyncio.Event | None = None) -> None:
    """主循环：手动 commit；失败满次进 DLQ。"""
    if not settings.kafka_bootstrap:
        logger.warning("KAFKA_BOOTSTRAP 未配置，跳过 analysis consumer")
        return

    consumer = AIOKafkaConsumer(
        settings.kafka_analysis_topic,
        bootstrap_servers=settings.kafka_bootstrap,
        group_id=settings.kafka_analysis_group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap)
    await consumer.start()
    await producer.start()
    logger.info(
        ingest_msg(
            _KIND,
            "00.consumer",
            f"status=started topic={settings.kafka_analysis_topic} group={settings.kafka_analysis_group}",
        )
    )
    try:
        while True:
            if stop_event and stop_event.is_set():
                break
            batch = await consumer.getmany(timeout_ms=1000, max_records=5)
            if not batch:
                continue
            for _tp, messages in batch.items():
                for msg in messages:
                    await _process_one(msg.value, producer)
            await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()
        logger.info(ingest_msg(_KIND, "00.consumer", "status=stopped"))


async def _process_one(raw: bytes | None, producer: AIOKafkaProducer) -> None:
    if raw is None:
        return
    try:
        event = AnalysisIngestEvent.model_validate_json(raw)
    except Exception:
        logger.exception(ingest_msg(_KIND, "10.consume_fail", "reason=invalid_event"))
        return

    logger.info(
        ingest_msg(
            _KIND,
            "10.consume",
            f"jobId={event.job_id} objectKey={event.object_key} "
            f"fileType={event.file_type} traceId={event.trace_id or ''}",
        ),
        extra={"trace_id": event.trace_id or ""},
    )

    retries = 0
    while True:
        try:
            await handle_analysis_ingest(event, retry_count=retries)
            return
        except Exception:
            retries += 1
            if retries >= settings.ingest_max_retries:
                logger.error(
                    ingest_msg(
                        _KIND,
                        "18.dlq",
                        f"jobId={event.job_id} retries={retries} action=send_dlq",
                    ),
                    extra={"trace_id": event.trace_id or ""},
                )
                await producer.send_and_wait(settings.kafka_analysis_dlq, raw)
                return
            logger.warning(
                ingest_msg(
                    _KIND,
                    "11.retry",
                    f"jobId={event.job_id} attempt={retries} max={settings.ingest_max_retries}",
                ),
                extra={"trace_id": event.trace_id or ""},
            )
            await asyncio.sleep(min(2**retries, 30))

"""Kafka Consumer：knowledge.ingest.v1。"""

from __future__ import annotations

import asyncio
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.config import settings
from app.observability.logging import ingest_msg
from app.rag.consumer.handlers.knowledge_ingest_handler import handle_knowledge_ingest
from app.rag.models.events import KnowledgeIngestEvent

logger = logging.getLogger(__name__)
_KIND = "knowledge"


async def run_knowledge_ingest_consumer(stop_event: asyncio.Event | None = None) -> None:
    if not settings.kafka_bootstrap:
        logger.warning("KAFKA_BOOTSTRAP 未配置，跳过 knowledge consumer")
        return

    consumer = AIOKafkaConsumer(
        settings.kafka_knowledge_topic,
        bootstrap_servers=settings.kafka_bootstrap,
        group_id=settings.kafka_ingest_group,
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
            f"status=started topic={settings.kafka_knowledge_topic} group={settings.kafka_ingest_group}",
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
        event = KnowledgeIngestEvent.model_validate_json(raw)
    except Exception:
        logger.exception(ingest_msg(_KIND, "10.consume_fail", "reason=invalid_event"))
        return

    logger.info(
        ingest_msg(
            _KIND,
            "10.consume",
            f"jobId={event.job_id} documentId={event.document_id} "
            f"objectKey={event.object_key} traceId={event.trace_id or ''}",
        ),
        extra={"trace_id": event.trace_id or ""},
    )

    retries = 0
    while True:
        try:
            await handle_knowledge_ingest(event, retry_count=retries)
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
                await producer.send_and_wait(settings.kafka_knowledge_dlq, raw)
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

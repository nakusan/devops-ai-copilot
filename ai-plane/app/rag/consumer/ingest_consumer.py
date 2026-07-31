"""Kafka Consumer：knowledge.ingest.v1。"""

from __future__ import annotations

import asyncio
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.config import settings
from app.rag.consumer.handlers.knowledge_ingest_handler import handle_knowledge_ingest
from app.rag.models.events import KnowledgeIngestEvent

logger = logging.getLogger(__name__)


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
        "knowledge consumer started topic=%s group=%s",
        settings.kafka_knowledge_topic,
        settings.kafka_ingest_group,
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
        logger.info("knowledge consumer stopped")


async def _process_one(raw: bytes | None, producer: AIOKafkaProducer) -> None:
    if raw is None:
        return
    try:
        event = KnowledgeIngestEvent.model_validate_json(raw)
    except Exception:
        logger.exception("invalid knowledge event, skip")
        return

    retries = 0
    while True:
        try:
            await handle_knowledge_ingest(event, retry_count=retries)
            return
        except Exception:
            retries += 1
            if retries >= settings.ingest_max_retries:
                logger.error("knowledge retries exhausted job_id=%s → DLQ", event.job_id)
                await producer.send_and_wait(settings.kafka_knowledge_dlq, raw)
                return
            await asyncio.sleep(min(2**retries, 30))

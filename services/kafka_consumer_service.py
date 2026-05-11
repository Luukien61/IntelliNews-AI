import json
import logging
import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional

from confluent_kafka import Consumer, KafkaError

from config import settings
from .ai_processor_service import ai_processor

logger = logging.getLogger(__name__)


class KafkaConsumerService:
    """
    Consumes Kafka events for AI processing.

    Uses two independent consumer loops (same consumer group, different client.id):
    - news.fetched-events  → summarization + embedding (can be slow)
    - tts.completed-events → persist audio paths + completion gate (fast)

    A single consumer polling both topics would interleave messages; TTS work
    still completes quickly, but splitting avoids any head-of-line coupling and
    keeps logs/latency easier to reason about.
    """

    def __init__(self) -> None:
        self._base_conf: Dict[str, Any] = {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id,
            "auto.offset.reset": settings.kafka_auto_offset_reset,
            "enable.auto.commit": True,
        }
        self._consumer_news: Optional[Consumer] = None
        self._consumer_tts: Optional[Consumer] = None
        self._running = False

    async def _consume_loop(
        self,
        *,
        topic: str,
        client_id: str,
        dispatch: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        conf = {**self._base_conf, "client.id": client_id}
        consumer = Consumer(conf)
        if topic == settings.kafka_topic_news_fetched:
            self._consumer_news = consumer
        else:
            self._consumer_tts = consumer

        consumer.subscribe([topic])
        logger.info("Kafka consumer started: topic=%s client.id=%s", topic, client_id)

        try:
            while self._running:
                msg = await asyncio.to_thread(consumer.poll, 1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Kafka error on %s: %s", topic, msg.error())
                    await asyncio.sleep(1)
                    continue

                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                    news_id = payload.get("newsId")
                    logger.info("Received %s: news_id=%s", topic, news_id)

                    if settings.kafka_event_concurrency:
                        asyncio.create_task(dispatch(payload))
                    else:
                        await dispatch(payload)
                except Exception as e:
                    logger.error("Failed to handle message from %s: %s", topic, e, exc_info=True)
        finally:
            # Stop sibling loop if this one exits (crash or shutdown).
            self._running = False
            consumer.close()
            logger.info("Kafka consumer stopped: topic=%s", topic)

    async def _dispatch_news(self, payload: Dict[str, Any]) -> None:
        await ai_processor.process_news_item(payload)

    async def _dispatch_tts(self, payload: Dict[str, Any]) -> None:
        await ai_processor.process_tts_completed_event(payload)

    async def start(self) -> None:
        self._running = True
        logger.info(
            "Kafka consumers starting (group.id=%s): %s | %s — concurrency=%s parallel=%s",
            settings.kafka_group_id,
            settings.kafka_topic_news_fetched,
            settings.kafka_topic_tts_completed,
            settings.kafka_event_concurrency,
            settings.ai_process_parallel,
        )
        try:
            results = await asyncio.gather(
                self._consume_loop(
                    topic=settings.kafka_topic_news_fetched,
                    client_id="intellinews-ai-news",
                    dispatch=self._dispatch_news,
                ),
                self._consume_loop(
                    topic=settings.kafka_topic_tts_completed,
                    client_id="intellinews-ai-tts",
                    dispatch=self._dispatch_tts,
                ),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, BaseException):
                    logger.error(
                        "Kafka consumer task ended with error: %s",
                        r,
                        exc_info=(type(r), r, r.__traceback__),
                    )
        except Exception as e:
            logger.error("Fatal error in Kafka consumers: %s", e, exc_info=True)
        finally:
            self._running = False
            self._consumer_news = None
            self._consumer_tts = None
            logger.info("Kafka consumer service exited.")

    def stop(self) -> None:
        self._running = False


kafka_consumer_service = KafkaConsumerService()

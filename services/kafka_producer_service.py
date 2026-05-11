"""
Kafka producer for IntelliNews-AI.

Publishes events to notify downstream services when all AI tasks
(summarization, embedding, TTS) are complete for a news item.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from confluent_kafka import Producer, KafkaException

from config import settings

logger = logging.getLogger(__name__)


class KafkaProducerService:
    """
    Thin wrapper around confluent_kafka.Producer.

    Produces messages synchronously with a short flush timeout so the caller
    gets confirmation before continuing.  All serialization is JSON.
    """

    def __init__(self):
        self._conf = {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "client.id": "intellinews-ai-producer",
            # Ensure at-least-once delivery
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 300,
        }
        self._producer: Optional[Producer] = None

    @property
    def producer(self) -> Producer:
        if self._producer is None:
            self._producer = Producer(self._conf)
            logger.info("Kafka producer initialised (bootstrap=%s)", settings.kafka_bootstrap_servers)
        return self._producer

    def _delivery_report(self, err, msg):
        if err:
            logger.error(
                "Kafka delivery failed: topic=%s key=%s error=%s",
                msg.topic(), msg.key(), err,
            )
        else:
            logger.debug(
                "Kafka message delivered: topic=%s partition=%d offset=%d key=%s",
                msg.topic(), msg.partition(), msg.offset(), msg.key(),
            )

    def publish(self, topic: str, key: str, payload: Dict[str, Any]) -> bool:
        """
        Publish *payload* as a JSON message to *topic* with *key*.
        Returns True on successful enqueue + flush, False on error.
        """
        try:
            value = json.dumps(payload, default=str).encode("utf-8")
            self.producer.produce(
                topic=topic,
                key=key.encode("utf-8"),
                value=value,
                callback=self._delivery_report,
            )
            # Flush with a 5-second timeout; remaining=0 means success.
            remaining = self.producer.flush(timeout=5)
            if remaining:
                logger.warning(
                    "Kafka flush: %d message(s) still in queue after timeout for topic=%s",
                    remaining, topic,
                )
                return False
            return True
        except KafkaException as exc:
            logger.error("KafkaException publishing to %s: %s", topic, exc)
            return False
        except Exception as exc:
            logger.error("Unexpected error publishing to %s: %s", topic, exc, exc_info=True)
            return False

    def publish_ai_processed(self, news_id: int) -> bool:
        """
        Emit a `news.ai-processed-events` message for *news_id*.
        The news-service consumes this to flip ai_processed=true.

        processedAt is sent as an ISO-8601 UTC string so Spring Boot's
        JavaTimeModule can deserialize it directly into java.time.Instant.
        """
        payload = {
            "newsId": news_id,
            "processedAt": datetime.now(timezone.utc).isoformat(),  # e.g. "2026-05-11T14:05:00.123456+00:00"
        }
        topic = settings.kafka_topic_ai_processed
        success = self.publish(topic, str(news_id), payload)
        if success:
            logger.info("Published ai-processed event for news_id=%d to topic=%s", news_id, topic)
        return success


# Singleton instance used across the application
kafka_producer_service = KafkaProducerService()

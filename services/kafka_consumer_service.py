import json
import logging
import asyncio
from typing import Optional
from confluent_kafka import Consumer, KafkaException, KafkaError

from config import settings
from .ai_processor_service import ai_processor

logger = logging.getLogger(__name__)

class KafkaConsumerService:
    """
    Consumes news fetched events from Kafka and initiates AI processing.
    """

    def __init__(self):
        self.conf = {
            'bootstrap.servers': settings.kafka_bootstrap_servers,
            'group.id': settings.kafka_group_id,
            'auto.offset.reset': settings.kafka_auto_offset_reset,
            'enable.auto.commit': True,
        }
        self.consumer: Optional[Consumer] = None
        self.topic_news_fetched = settings.kafka_topic_news_fetched
        self.topic_tts_completed = getattr(settings, 'kafka_topic_tts_completed', "tts.completed-events")
        self._running = False

    async def start(self):
        """Start Kafka consumer loop asynchronously."""
        self.consumer = Consumer(self.conf)
        self.consumer.subscribe([self.topic_news_fetched, self.topic_tts_completed])
        self._running = True
        logger.info(f"Kafka consumer started. Subscribed to topics: {self.topic_news_fetched}, {self.topic_tts_completed}")
        logger.info(f"Concurrency: {settings.kafka_event_concurrency}, Task Parallelism: {settings.ai_process_parallel}")

        try:
            while self._running:
                # Use a small timeout to avoid blocking too long
                msg = await asyncio.to_thread(self.consumer.poll, 1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka Error: {msg.error()}")
                        await asyncio.sleep(1)
                        continue
                
                # Process message
                try:
                    payload = json.loads(msg.value().decode('utf-8'))
                    topic = msg.topic()
                    news_id = payload.get('newsId')
                    
                    if topic == self.topic_news_fetched:
                        logger.info(f"Received news event: news_id={news_id}")
                        if settings.kafka_event_concurrency:
                            # Process multiple news items at once
                            asyncio.create_task(ai_processor.process_news_item(payload))
                        else:
                            # Process one news item at a time
                            await ai_processor.process_news_item(payload)
                    elif topic == self.topic_tts_completed:
                        logger.info(f"Received TTS completed event: news_id={news_id}")
                        if settings.kafka_event_concurrency:
                            asyncio.create_task(ai_processor.process_tts_completed_event(payload))
                        else:
                            await ai_processor.process_tts_completed_event(payload)
                    
                except Exception as e:
                    logger.error(f"Failed to parse or handle message: {e}")

        except Exception as e:
            logger.error(f"Fatal error in consumer: {e}")
        finally:
            self._running = False
            if self.consumer:
                self.consumer.close()
            logger.info("Kafka consumer stopped.")

    def stop(self):
        """Stop the consumer loop."""
        self._running = False


kafka_consumer_service = KafkaConsumerService()

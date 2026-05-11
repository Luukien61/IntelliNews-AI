import asyncio
import concurrent.futures
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from config import settings
from services.cpu_limiter import set_torch_threads
from db.database import SessionLocal
from db.models import NewsAIResult, NewsEmbedding
from services.recommendation import recommendation_service
from services.summarization.service import summarization_service
from services.utils.text import clean_text_for_ai

logger = logging.getLogger(__name__)


class AIProcessorService:
    """
    Coordinates AI processing (Summarization, Embedding, TTS) for news items.

    Completion gate
    ---------------
    A news item is considered *fully processed* only when ALL three tasks are done:
      1. Summarization  ─┐ both triggered by `news.fetched-events`
      2. Embedding       ─┘
      3. TTS audio       ── triggered later by `tts.completed-events`

    After each step we call `_check_and_emit_if_complete()`.  That method reads
    the DB to see whether the other side is already finished, and if so it emits
    a single `news.ai-processed-events` Kafka message.  The news-service consumes
    that message and flips `ai_processed = true`, making the item visible to clients.
    """

    def __init__(self):
        max_workers = min(settings.ai_process_max_workers, settings.ai_max_cores)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.active_tasks = 0

        set_torch_threads(settings.ai_max_cores)

        logger.info(
            "AIProcessorService initialised with max_workers=%d (ai_max_cores=%d)",
            max_workers, settings.ai_max_cores,
        )

    # ------------------------------------------------------------------
    # Public entry points (called by KafkaConsumerService)
    # ------------------------------------------------------------------

    async def process_news_item(self, event_data: Dict[str, Any]):
        """
        Triggered by `news.fetched-events`.

        Runs summarization and embedding, then checks whether TTS is already
        complete.  If yes, emits the all-done Kafka event immediately.
        """
        news_id = event_data.get("newsId")
        title = event_data.get("title", "")
        description = event_data.get("description", "")
        content = event_data.get("contentPlainText", "")
        category = event_data.get("category", "UNKNOWN")
        published_at_raw = event_data.get("publishedAt")

        published_at = None
        if published_at_raw:
            published_at = datetime.fromtimestamp(float(published_at_raw), tz=timezone.utc)

        if news_id is None or not content:
            logger.error("Invalid event data: %s", event_data)
            return

        self.active_tasks += 1
        news_id_int = int(news_id)
        logger.info("Processing news_id=%d (parallel=%s)", news_id_int, settings.ai_process_parallel)

        try:
            # Run summarization + embedding (parallel or sequential per config)
            if settings.ai_process_parallel:
                logger.info("Starting Summarization + Embedding in parallel for news_id=%d", news_id_int)
                await asyncio.gather(
                    self._run_summarization(news_id_int, content),
                    self._run_embedding(news_id_int, title, description, category, published_at),
                )
            else:
                logger.info("Starting Summarization for news_id=%d", news_id_int)
                await self._run_summarization(news_id_int, content)
                logger.info("Starting Embedding for news_id=%d", news_id_int)
                await self._run_embedding(news_id_int, title, description, category, published_at)

            logger.info("Summarization + Embedding done for news_id=%d", news_id_int)

            # Gate: emit only if TTS is already done too
            await asyncio.to_thread(self._check_and_emit_if_complete, news_id_int)

        except Exception as e:
            logger.error("Error processing news_id=%d: %s", news_id_int, e, exc_info=True)
        finally:
            self.active_tasks -= 1

    async def process_tts_completed_event(self, event_data: Dict[str, Any]):
        """
        Triggered by `tts.completed-events`.

        Saves audio filenames to `news_ai_results`, then checks whether
        summarization + embedding are already complete.  If yes, emits the
        all-done Kafka event.
        """
        news_id = event_data.get("newsId")
        if news_id is None:
            logger.error("Missing newsId in TTS completed event")
            return

        news_id_int = int(news_id)
        audio_files_data = event_data.get("audioFiles", [])

        audio_key = settings.tts_event_audio_key
        filenames = [f.get(audio_key) for f in audio_files_data if f.get(audio_key)]

        if not filenames:
            logger.warning(
                "No valid items found using key '%s' in TTS event for news_id=%d",
                audio_key, news_id_int,
            )
            return

        logger.info("Saving TTS audio for news_id=%d: %s", news_id_int, filenames)
        await asyncio.to_thread(self._save_tts_completed_filenames, news_id_int, filenames)

        # Gate: emit only if summarization + embedding are already done too
        await asyncio.to_thread(self._check_and_emit_if_complete, news_id_int)

    # ------------------------------------------------------------------
    # Private helpers — AI tasks
    # ------------------------------------------------------------------

    async def _run_summarization(self, news_id: int, content: str):
        """Generate summaries and store in DB."""
        db = SessionLocal()
        try:
            await summarization_service.get_or_generate_summaries(
                news_id, db, force=True, content_text=content
            )
        finally:
            db.close()

    async def _run_embedding(
        self,
        news_id: int,
        title: str,
        description: str,
        category: str,
        published_at,
    ):
        """Generate title + description embedding and store in DB."""
        db = SessionLocal()
        try:
            existing = db.query(NewsEmbedding).filter(NewsEmbedding.news_id == news_id).first()
            if existing:
                return

            text = f"{title} {description}" if description else title
            text = clean_text_for_ai(text)
            embedding = await asyncio.to_thread(recommendation_service.generate_embedding, text)

            news_embedding = NewsEmbedding(
                news_id=news_id,
                category=category,
                title=title,
                embedding=embedding,
                published_at=published_at,
            )
            db.add(news_embedding)
            db.commit()
        except Exception as e:
            logger.error("Embedding failed for news_id=%d: %s", news_id, e)
            db.rollback()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Private helpers — TTS persistence
    # ------------------------------------------------------------------

    def _save_tts_completed_filenames(self, news_id: int, filenames: list):
        """Upsert TTS filenames into NewsAIResult."""
        from sqlalchemy.sql import func

        db = SessionLocal()
        try:
            existing = db.query(NewsAIResult).filter(NewsAIResult.news_id == news_id).first()
            if existing:
                existing.audio_files = filenames
                existing.updated_at = func.now()
            else:
                existing = NewsAIResult(news_id=news_id, audio_files=filenames)
                db.add(existing)
            db.commit()
            logger.info("Saved TTS filenames for news_id=%d", news_id)
        except Exception as e:
            logger.error("Failed to save TTS result for news_id=%d: %s", news_id, e)
            db.rollback()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Completion gate
    # ------------------------------------------------------------------

    def _check_and_emit_if_complete(self, news_id: int) -> None:
        """
        Reads the DB to determine whether ALL three AI tasks are complete:
          • Summarization  → NewsAIResult.summary_short  is not None
          • Embedding      → NewsEmbedding row exists
          • TTS            → NewsAIResult.audio_files is a non-empty list

        If all three conditions are met, publishes one `news.ai-processed-events`
        Kafka message so the news-service can flip ai_processed=true.

        This method is intentionally synchronous (called via asyncio.to_thread)
        to keep DB access simple and avoid session-sharing issues.
        """
        db = SessionLocal()
        try:
            ai_result = db.query(NewsAIResult).filter(NewsAIResult.news_id == news_id).first()
            embedding = db.query(NewsEmbedding).filter(NewsEmbedding.news_id == news_id).first()

            summarization_done = (
                ai_result is not None
                and ai_result.summary_short is not None
            )
            embedding_done = embedding is not None
            tts_done = (
                ai_result is not None
                and isinstance(ai_result.audio_files, list)
                and len(ai_result.audio_files) > 0
            )

            logger.info(
                "Completion check for news_id=%d: summarization=%s, embedding=%s, tts=%s",
                news_id, summarization_done, embedding_done, tts_done,
            )

            if summarization_done and embedding_done and tts_done:
                self._emit_ai_processed(news_id)
            else:
                logger.info(
                    "news_id=%d not fully processed yet — waiting for remaining tasks.",
                    news_id,
                )
        except Exception as e:
            logger.error(
                "Error during completion check for news_id=%d: %s", news_id, e, exc_info=True
            )
        finally:
            db.close()

    @staticmethod
    def _emit_ai_processed(news_id: int) -> None:
        """Publish the all-done Kafka event (import here to avoid circular imports)."""
        from services.kafka_producer_service import kafka_producer_service

        logger.info("All AI tasks complete for news_id=%d — emitting ai-processed event.", news_id)
        kafka_producer_service.publish_ai_processed(news_id)


ai_processor = AIProcessorService()

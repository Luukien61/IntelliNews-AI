import asyncio
import concurrent.futures
import logging
from typing import Dict, Any

from config import settings
from db.database import SessionLocal
from db.models import NewsAIResult, NewsEmbedding
from services.recommendation import recommendation_service
from services.summarization.service import summarization_service

logger = logging.getLogger(__name__)

class AIProcessorService:
    """
    Coordinates AI processing (Summarization, TTS, Embedding) for news items.
    Can run tasks sequentially or in parallel.
    """

    def __init__(self):
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.ai_process_max_workers
        )

    async def process_news_item(self, event_data: Dict[str, Any]):
        """
        Process a single news item from Kafka event.
        
        Order: TTS (Priority) -> (Summarization, Embedding).
        Can be run in parallel (Summarization + Embedding) or sequentially.
        """
        news_id = event_data.get("newsId")
        title = event_data.get("title", "")
        content = event_data.get("contentPlainText", "")
        category = event_data.get("category", "UNKNOWN")

        if news_id is None or not content:
            logger.error(f"Invalid event data: {event_data}")
            return

        # Explicitly cast to int to satisfy type checker
        news_id_int = int(news_id)

        logger.info(f"Processing news_id={news_id_int} (parallel tasks: {settings.ai_process_parallel})")

        try:
            # # 1. TTS - priority
            # # We process this first as requested
            # logger.info(f"Step 1: Starting TTS for news_id={news_id_int}")
            # # synthesize is sync, use to_thread
            # tts_result = await asyncio.to_thread(tts_service.synthesize, content)
            # logger.info(f"TTS completed for news_id={news_id_int}: {tts_result.get('filename')}")
            #
            # # Save TTS result in DB
            # self._save_tts_result(news_id_int, tts_result)

            # 2. Summarization and Embedding
            if settings.ai_process_parallel:
                logger.info(f"Step 2: Starting Summarization and Embedding in parallel for news_id={news_id_int}")
                await asyncio.gather(
                    self._run_summarization(news_id_int, content),
                    self._run_embedding(news_id_int, title, category)
                )
            else:
                logger.info(f"Step 2: Starting Summarization for news_id={news_id_int}")
                await self._run_summarization(news_id_int, content)
                logger.info(f"Step 3: Starting Embedding for news_id={news_id_int}")
                await self._run_embedding(news_id_int, title, category)

            logger.info(f"Successfully processed all AI tasks for news_id={news_id_int}")

        except Exception as e:
            logger.error(f"Error processing news_id={news_id_int}: {e}", exc_info=True)

    async def _run_summarization(self, news_id: int, content: str):
        """Generate summaries and store in DB."""
        # The existing news_summarization_service expects to fetch content.
        db = SessionLocal()
        try:
            await summarization_service.get_or_generate_summaries(
                news_id, db, force=True, content_text=content
            )
        finally:
            db.close()

    async def _run_embedding(self, news_id: int, title: str, category: str):
        """Generate title embedding and store in DB."""
        # Check if already indexed
        db = SessionLocal()
        try:
            existing = db.query(NewsEmbedding).filter(
                NewsEmbedding.news_id == news_id
            ).first()
            if existing:
                return

            embedding = await asyncio.to_thread(recommendation_service.generate_embedding, title)
            
            news_embedding = NewsEmbedding(
                news_id=news_id,
                category=category,
                title=title,
                embedding=embedding
            )
            db.add(news_embedding)
            db.commit()
        except Exception as e:
            logger.error(f"Embedding failed for news_id={news_id}: {e}")
            db.rollback()
        finally:
            db.close()

    def _save_tts_result(self, news_id: int, tts_result: Dict[str, Any]):
        """Save TTS result URL to NewsAIResult."""
        db = SessionLocal()
        try:
            existing = db.query(NewsAIResult).filter(
                NewsAIResult.news_id == news_id
            ).first()
            
            s3_url = tts_result.get("s3_url")
            if not s3_url:
                logger.warning(f"No S3 URL in TTS result for news_id={news_id}")
                return

            if existing:
                audio_files = list(existing.audio_files or [])
                if s3_url not in audio_files:
                    audio_files.append(s3_url)
                    existing.audio_files = audio_files
            else:
                existing = NewsAIResult(
                    news_id=news_id,
                    audio_files=[s3_url]
                )
                db.add(existing)
            
            db.commit()
        except Exception as e:
            logger.error(f"Failed to save TTS result to DB: {e}")
            db.rollback()
        finally:
            db.close()

ai_processor = AIProcessorService()

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
    Coordinates AI processing (Summarization, TTS, Embedding) for news items.
    Can run tasks sequentially or in parallel.
    
    Respects ai_max_cores setting to limit CPU usage during intensive operations.
    Tracks active_tasks to coordinate with clustering scheduler.
    """

    def __init__(self):
        # Limit thread pool based on ai_max_cores setting
        max_workers = min(settings.ai_process_max_workers, settings.ai_max_cores)
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        )
        self.active_tasks = 0
        
        # Set PyTorch thread limit (if torch is available)
        set_torch_threads(settings.ai_max_cores)
        
        logger.info(
            f"AIProcessorService initialized with max_workers={max_workers} "
            f"(ai_max_cores={settings.ai_max_cores})"
        )

    async def process_news_item(self, event_data: Dict[str, Any]):
        """
        Process a single news item from Kafka event.
        
        Order: TTS (Priority) -> (Summarization, Embedding).
        Can be run in parallel (Summarization + Embedding) or sequentially.
        """
        news_id = event_data.get("newsId")
        title = event_data.get("title", "")
        description = event_data.get("description", "")
        content = event_data.get("contentPlainText", "")
        category = event_data.get("category", "UNKNOWN")
        published_at_raw = event_data.get("publishedAt")

        published_at = None
        if published_at_raw:
            published_at = datetime.fromtimestamp(
                float(published_at_raw),
                tz=timezone.utc
            )

        if news_id is None or not content:
            logger.error(f"Invalid event data: {event_data}")
            return

        self.active_tasks += 1

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
                    self._run_embedding(news_id_int, title, description, category, published_at)
                )
            else:
                logger.info(f"Step 2: Starting Summarization for news_id={news_id_int}")
                await self._run_summarization(news_id_int, content)
                logger.info(f"Step 3: Starting Embedding for news_id={news_id_int}")
                await self._run_embedding(news_id_int, title, description, category, published_at)

            logger.info(f"Successfully processed all AI tasks for news_id={news_id_int}")

        except Exception as e:
            logger.error(f"Error processing news_id={news_id_int}: {e}", exc_info=True)
        finally:
            self.active_tasks -= 1

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

    async def _run_embedding(self, news_id: int, title: str, description: str, category: str, published_at):
        """Generate title + description embedding and store in DB."""
        # Check if already indexed
        db = SessionLocal()
        try:
            existing = db.query(NewsEmbedding).filter(
                NewsEmbedding.news_id == news_id
            ).first()
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
                published_at=published_at
            )
            db.add(news_embedding)
            db.commit()
        except Exception as e:
            logger.error(f"Embedding failed for news_id={news_id}: {e}")
            db.rollback()
        finally:
            db.close()



    async def process_tts_completed_event(self, event_data: Dict[str, Any]):
        """Process TTS completed event to update audio_files in DB."""
        news_id = event_data.get("newsId")
        if news_id is None:
            logger.error("Missing newsId in TTS completed event")
            return
            
        news_id_int = int(news_id)
        audio_files_data = event_data.get("audioFiles", [])
        
        # Extract filenames using the configured key
        audio_key = settings.tts_event_audio_key
        filenames = [f.get(audio_key) for f in audio_files_data if f.get(audio_key)]
        
        if not filenames:
            logger.warning(f"No valid items found using key '{audio_key}' in TTS event for news_id={news_id_int}")
            return
            
        logger.info(f"Updating TTS result for news_id={news_id_int} with files: {filenames}")
        
        await asyncio.to_thread(self._save_tts_completed_filenames, news_id_int, filenames)

    def _save_tts_completed_filenames(self, news_id: int, filenames: list):
        """Save TTS completed filenames to NewsAIResult."""
        db = SessionLocal()
        try:
            from sqlalchemy.sql import func
            existing = db.query(NewsAIResult).filter(
                NewsAIResult.news_id == news_id
            ).first()
            
            if existing:
                existing.audio_files = filenames
                existing.updated_at = func.now()
            else:
                existing = NewsAIResult(
                    news_id=news_id,
                    audio_files=filenames
                )
                db.add(existing)
            
            db.commit()
        except Exception as e:
            logger.error(f"Failed to save TTS completed result to DB: {e}")
            db.rollback()
        finally:
            db.close()

ai_processor = AIProcessorService()

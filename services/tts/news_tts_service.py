"""News TTS Service - Generate TTS audio for news articles."""
import logging
from typing import List, Optional

import redis.asyncio as aioredis
from sqlalchemy.orm import Session

from config import settings
from db.models import NewsAIResult
from services.constants import (
    FIELD_CONTENT_PLAIN_TEXT,
    TTS_PREFIX_KEY,
    KEY_VOICE_ID,
    KEY_DESCRIPTION,
    KEY_URL,
    KEY_S3_KEY,
    KEY_S3_URL,
    KEY_PRESIGNED_URL,
    KEY_FILENAME
)
from services.news_client import news_client
from services.tts.service import tts_service
from services.tts.storage import tts_storage

logger = logging.getLogger(__name__)

# Available TTS voices with descriptions
AVAILABLE_VOICES = [
    {KEY_VOICE_ID: "Doan", KEY_DESCRIPTION: "Giọng nữ miền Nam"},
    {KEY_VOICE_ID: "Binh", KEY_DESCRIPTION: "Giọng nam miền Bắc"},
]


class NewsTTSService:
    """
    Service to generate and manage TTS audio for news articles.
    
    Features:
    - Check existing audio in database (caching)
    - Fetch content from news-service
    - Generate audio for multiple voices
    - Upload to MinIO and save to database
    """

    def __init__(self, voices: Optional[List[dict]] = None):
        """
        Initialize NewsTTSService.
        
        Args:
            voices: List of voice configurations. Defaults to AVAILABLE_VOICES.
        """
        self.voices = voices or AVAILABLE_VOICES
        self._redis = None

    async def _get_redis(self):
        """Get or create Redis connection (lazy initialization)."""
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.redis_url,
                    decode_responses=False
                )
                # Test connection
                await self._redis.ping()
                logger.info(f"Redis connected: {settings.redis_url}")
            except Exception as e:
                logger.warning(f"Redis not available: {e}")
                self._redis = None
        return self._redis

    async def _get_presigned_url_cached(self, s3_key: str) -> Optional[str]:
        """
        Get presigned URL from Redis cache or generate a new one.
        """
        if not s3_key:
            return None

        redis_key = f"{TTS_PREFIX_KEY}:{s3_key}"
        redis = await self._get_redis()

        # 1. Try to get from Redis
        if redis:
            try:
                cached_url = await redis.get(redis_key)
                if cached_url:
                    return cached_url.decode("utf-8")
            except Exception as e:
                logger.warning(f"Failed to read from Redis: {e}")

        # 2. Generate new URL
        # Default expiration 24 hours (86400s)
        expiration = 86400
        url = tts_storage.generate_presigned_url(s3_key, expiration=expiration)

        if not url:
            return None

        # 3. Save to Redis
        if redis:
            try:
                # Cache for slightly less time than expiration to be safe
                await redis.set(redis_key, url, ex=expiration - 60)
            except Exception as e:
                logger.warning(f"Failed to write to Redis: {e}")

        return url

    async def get_or_generate_audio(
            self,
            news_id: int,
            db: Session
    ) -> tuple[List[dict], bool]:
        """
        Get existing audio or generate new TTS audio for a news article.
        
        Args:
            news_id: ID of the news item
            db: Database session
            
        Returns:
            Tuple of (list of audio info dicts, cached: bool)
            
        Raises:
            ValueError: If news item not found
            RuntimeError: If TTS generation fails
        """
        # 1. Check if audio already exists in database
        existing = db.query(NewsAIResult).filter(NewsAIResult.news_id == news_id).first()
        if existing and existing.audio_files:
            logger.info(f"Found cached audio for news_id={news_id}")
            # Enrich with presigned URLs from Redis
            for audio in existing.audio_files:
                if KEY_S3_KEY in audio:
                    audio[KEY_PRESIGNED_URL] = await self._get_presigned_url_cached(audio[KEY_S3_KEY])
            return existing.audio_files, True

        # 2. Fetch content from news-service
        logger.info(f"Fetching content for news_id={news_id}")
        try:
            content_data = await news_client.get_news_content(
                news_id=news_id,
                fields=[FIELD_CONTENT_PLAIN_TEXT]
            )
        except Exception as e:
            logger.error(f"Failed to fetch news content: {e}")
            raise ValueError(f"News item not found or cannot fetch: {news_id}")

        content_text = content_data.get(FIELD_CONTENT_PLAIN_TEXT)
        if not content_text:
            raise ValueError(f"News item {news_id} has no content")

        # 3. Generate audio for each voice
        logger.info(f"Generating TTS audio for news_id={news_id} with {len(self.voices)} voices")
        audio_files = []

        for voice in self.voices:
            try:
                logger.info(f"Generating audio with voice: {voice[KEY_VOICE_ID]}")
                result = tts_service.synthesize(
                    text=content_text,
                    voice_id=voice[KEY_VOICE_ID],
                    upload_to_s3=True
                )

                audio_info = {
                    KEY_VOICE_ID: voice[KEY_VOICE_ID],
                    KEY_DESCRIPTION: voice[KEY_DESCRIPTION],
                    KEY_URL: result.get(KEY_S3_URL),
                    KEY_S3_KEY: result.get(KEY_S3_KEY),
                    KEY_FILENAME: result.get(KEY_FILENAME)
                }

                # Cache the generated presigned url immediately if available
                if result.get(KEY_S3_KEY) and result.get(KEY_PRESIGNED_URL):
                    await self._cache_presigned_url(result.get(KEY_S3_KEY), result.get(KEY_PRESIGNED_URL))

                audio_files.append(audio_info)
                logger.info(f"Successfully generated audio: {audio_info[KEY_S3_KEY]}")

            except Exception as e:
                logger.error(f"Failed to generate audio with voice {voice[KEY_VOICE_ID]}: {e}")
                raise RuntimeError(f"TTS generation failed for voice {voice[KEY_VOICE_ID]}: {e}")

        # 4. Save to database
        if existing:
            # Update existing record
            existing.audio_files = audio_files
            db.commit()
            db.refresh(existing)
            logger.info(f"Updated audio record for news_id={news_id}")
        else:
            # Create new record
            news_ai_result = NewsAIResult(
                news_id=news_id,
                audio_files=audio_files
            )
            db.add(news_ai_result)
            db.commit()
            db.refresh(news_ai_result)
            logger.info(f"Created new AI result record for news_id={news_id}")

        # Add presigned URLs to response
        for audio in audio_files:
            if KEY_S3_KEY in audio:
                audio[KEY_PRESIGNED_URL] = await self._get_presigned_url_cached(audio[KEY_S3_KEY])

        return audio_files, False

    async def _cache_presigned_url(self, s3_key: str, url: str):
        """Helper to cache a freshly generated URL"""
        try:
            redis = await self._get_redis()
            if redis:
                await redis.set(f"{TTS_PREFIX_KEY}:{s3_key}", url, ex=86400 - 60)
        except Exception as e:
            logger.warning(f"Failed to cache generated URL: {e}")

    async def get_cached_audio(self, news_id: int, db: Session) -> Optional[List[dict]]:
        """
        Get cached audio files for a news item without generating.
        
        Args:
            news_id: ID of the news item
            db: Database session
            
        Returns:
            List of audio info dicts or None if not cached
        """
        existing = db.query(NewsAIResult).filter(NewsAIResult.news_id == news_id).first()
        if existing and existing.audio_files:
            # Enrich with presigned URLs from Redis
            result_files = []
            for audio in existing.audio_files:
                # Create a copy to avoid modifying the DB object directly if it's attached
                audio_data = audio.copy()
                if KEY_S3_KEY in audio_data:
                    audio_data[KEY_PRESIGNED_URL] = await self._get_presigned_url_cached(audio_data[KEY_S3_KEY])
                result_files.append(audio_data)
            return result_files
        return None

    async def delete_audio(self, news_id: int, db: Session) -> bool:
        """
        Delete cached audio for a news item.
        
        Args:
            news_id: ID of the news item
            db: Database session
            
        Returns:
            True if deleted, False if not found
        """
        existing = db.query(NewsAIResult).filter(NewsAIResult.news_id == news_id).first()
        if existing:
            # Also delete keys from Redis
            if existing.audio_files:
                redis = await self._get_redis()
                if redis:
                    for audio in existing.audio_files:
                        s3_key = audio.get(KEY_S3_KEY)
                        if s3_key:
                            try:
                                await redis.delete(f"{TTS_PREFIX_KEY}:{s3_key}")
                            except Exception:
                                pass

            # TODO: Also delete files from MinIO
            db.delete(existing)
            db.commit()
            logger.info(f"Deleted AI result record for news_id={news_id}")
            return True
        return False


# Global service instance
news_tts_service = NewsTTSService()

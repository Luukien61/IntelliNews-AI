"""News TTS Service - Generate TTS audio for news articles."""
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from config import settings
from db.models import NewsAIResult
from services.news_client import news_client
from services.tts.service import tts_service
from services.constants import FIELD_CONTENT_PLAIN_TEXT

logger = logging.getLogger(__name__)

# Available TTS voices with descriptions
AVAILABLE_VOICES = [
    {"voice_id": "Binh", "description": "Giọng nam miền Bắc"},
    {"voice_id": "Doan", "description": "Giọng nữ miền Nam"},
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
                logger.info(f"Generating audio with voice: {voice['voice_id']}")
                result = tts_service.synthesize(
                    text=content_text,
                    voice_id=voice["voice_id"],
                    upload_to_s3=True
                )

                audio_info = {
                    "voice_id": voice["voice_id"],
                    "description": voice["description"],
                    "url": result.get("s3_url"),
                    "s3_key": result.get("s3_key"),
                    "presigned_url": result.get("presigned_url"),
                    "filename": result.get("filename")
                }
                audio_files.append(audio_info)
                logger.info(f"Successfully generated audio: {audio_info['s3_key']}")

            except Exception as e:
                logger.error(f"Failed to generate audio with voice {voice['voice_id']}: {e}")
                raise RuntimeError(f"TTS generation failed for voice {voice['voice_id']}: {e}")

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

        return audio_files, False

    def get_cached_audio(self, news_id: int, db: Session) -> Optional[List[dict]]:
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
            return existing.audio_files
        return None

    def delete_audio(self, news_id: int, db: Session) -> bool:
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
            # TODO: Also delete files from MinIO
            db.delete(existing)
            db.commit()
            logger.info(f"Deleted AI result record for news_id={news_id}")
            return True
        return False


# Global service instance
news_tts_service = NewsTTSService()

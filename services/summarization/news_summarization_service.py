"""News Summarization Service - orchestrates summarization for news articles."""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from db.models import NewsAIResult
from services.news_client import news_client
from services.constants import (
    FIELD_CONTENT_PLAIN_TEXT,
    KEY_NEWS_ID,
    KEY_SUMMARY_SHORT,
    KEY_SUMMARY_DEFAULT,
)

logger = logging.getLogger(__name__)

# Lazy-loaded summarizer singletons
_phobert_summarizer = None
_vit5_summarizer = None
_position_summarizer = None


def get_phobert_summarizer():
    """Lazy-load PhoBERT summarizer (heavy model)."""
    global _phobert_summarizer
    if _phobert_summarizer is None:
        from .phobert_summarizer import PhoBERTSummarizer
        _phobert_summarizer = PhoBERTSummarizer(
            model_name=settings.phobert_model_name
        )
    return _phobert_summarizer


def get_vit5_summarizer():
    """Lazy-load ViT5 summarizer (heavy model)."""
    global _vit5_summarizer
    if _vit5_summarizer is None:
        from .vit5_summarizer import ViT5Summarizer
        _vit5_summarizer = ViT5Summarizer(
            model_name=settings.vit5_model_name
        )
    return _vit5_summarizer


def get_position_summarizer():
    """Lazy-load Position summarizer (lightweight)."""
    global _position_summarizer
    if _position_summarizer is None:
        from .position_summarizer import PositionSummarizer
        _position_summarizer = PositionSummarizer()
    return _position_summarizer


class NewsSummarizationService:
    """
    Orchestrates summarization for news articles.
    
    Workflow:
    1. Check DB cache for existing summaries
    2. Fetch content from news-service
    3. Run ViT5 → summary_short
    4. Run PhoBERT → summary_default
    5. Upsert NewsAIResult and return
    """

    async def get_or_generate_summaries(
        self,
        news_id: int,
        db: Session,
        force: bool = False
    ) -> tuple[dict, bool]:
        """
        Get existing summaries or generate new ones.

        Args:
            news_id: ID of the news item
            db: Database session
            force: If True, regenerate even if cached

        Returns:
            Tuple of (result dict, cached: bool)

        Raises:
            ValueError: If news item not found or has no content
            RuntimeError: If summarization fails
        """
        # 1. Check cache
        existing = db.query(NewsAIResult).filter(
            NewsAIResult.news_id == news_id
        ).first()

        if (
            not force
            and existing
            and existing.summary_short
            and existing.summary_default
        ):
            logger.info(f"Found cached summaries for news_id={news_id}")
            return {
                KEY_NEWS_ID: news_id,
                KEY_SUMMARY_SHORT: existing.summary_short,
                KEY_SUMMARY_DEFAULT: existing.summary_default,
            }, True

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

        # 3. Run ViT5 → summary_short
        logger.info(f"Generating ViT5 summary for news_id={news_id}")
        try:
            vit5 = get_vit5_summarizer()
            summary_short = vit5.summarize(content_text)
        except Exception as e:
            logger.error(f"ViT5 summarization failed: {e}")
            # Fallback to position-based
            logger.info("Falling back to Position-based summarizer for summary_short")
            position = get_position_summarizer()
            summary_short = position.summarize(content_text, ratio=0.2)

        # 4. Run PhoBERT → summary_default
        logger.info(f"Generating PhoBERT summary for news_id={news_id}")
        try:
            phobert = get_phobert_summarizer()
            summary_default = phobert.summarize(content_text)
        except Exception as e:
            logger.error(f"PhoBERT summarization failed: {e}")
            # Fallback to position-based
            logger.info("Falling back to Position-based summarizer for summary_default")
            position = get_position_summarizer()
            summary_default = position.summarize(content_text, ratio=0.3)

        # 5. Upsert into database
        result_data = {
            KEY_NEWS_ID: news_id,
            KEY_SUMMARY_SHORT: summary_short,
            KEY_SUMMARY_DEFAULT: summary_default,
        }

        if existing:
            existing.summary_short = summary_short
            existing.summary_default = summary_default
            db.commit()
            db.refresh(existing)
            logger.info(f"Updated summaries for news_id={news_id}")
        else:
            news_ai_result = NewsAIResult(
                news_id=news_id,
                summary_short=summary_short,
                summary_default=summary_default,
                audio_files=[],
            )
            db.add(news_ai_result)
            db.commit()
            db.refresh(news_ai_result)
            logger.info(f"Created new AI result with summaries for news_id={news_id}")

        return result_data, False

    def get_cached_summaries(
        self, news_id: int, db: Session
    ) -> Optional[dict]:
        """Get cached summaries without generating."""
        existing = db.query(NewsAIResult).filter(
            NewsAIResult.news_id == news_id
        ).first()
        if existing and (existing.summary_short or existing.summary_default):
            return {
                KEY_NEWS_ID: news_id,
                KEY_SUMMARY_SHORT: existing.summary_short,
                KEY_SUMMARY_DEFAULT: existing.summary_default,
            }
        return None


# Global service instance
news_summarization_service = NewsSummarizationService()

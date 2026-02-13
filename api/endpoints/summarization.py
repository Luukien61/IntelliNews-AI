"""Summarization API endpoints."""
import logging

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from services.summarization.models import NewsSummarizationResponse
from services.summarization.news_summarization_service import news_summarization_service
from services.constants import (
    KEY_NEWS_ID,
    KEY_SUMMARY_SHORT,
    KEY_SUMMARY_DEFAULT,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summarization", tags=["Summarization"])


@router.post("/news/{news_id}", response_model=NewsSummarizationResponse)
async def summarize_news(
    news_id: int,
    force: bool = Query(
        default=False,
        description="Force regeneration even if cached summaries exist"
    ),
    db: Session = Depends(get_db),
):
    """
    Generate summaries for a news article.

    - Fetches the news content from the news-service
    - Runs ViT5 abstractive summarizer → saved to `summary_short`
    - Runs PhoBERT extractive summarizer → saved to `summary_default`
    - Saves results to database and returns them

    Args:
        news_id: ID of the news item to summarize
        force: If True, regenerate even if summaries already exist
        db: Database session (injected)

    Returns:
        NewsSummarizationResponse with both summaries
    """
    try:
        logger.info(f"Summarization request for news_id={news_id}, force={force}")

        result, cached = await news_summarization_service.get_or_generate_summaries(
            news_id=news_id,
            db=db,
            force=force,
        )

        return NewsSummarizationResponse(
            success=True,
            news_id=result[KEY_NEWS_ID],
            summary_short=result[KEY_SUMMARY_SHORT],
            summary_default=result[KEY_SUMMARY_DEFAULT],
            cached=cached,
            message="Summaries retrieved from cache" if cached else "Summaries generated successfully",
        )

    except ValueError as e:
        logger.error(f"Summarization input error: {e}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summaries: {str(e)}"
        )


@router.get("/news/{news_id}", response_model=NewsSummarizationResponse)
async def get_summaries(
    news_id: int,
    db: Session = Depends(get_db),
):
    """
    Get cached summaries for a news article (no generation).

    Returns 404 if no cached summaries exist.
    """
    result = news_summarization_service.get_cached_summaries(news_id, db)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No cached summaries found for news_id={news_id}"
        )

    return NewsSummarizationResponse(
        success=True,
        news_id=result[KEY_NEWS_ID],
        summary_short=result[KEY_SUMMARY_SHORT],
        summary_default=result[KEY_SUMMARY_DEFAULT],
        cached=True,
        message="Summaries retrieved from cache",
    )


@router.get("/health")
async def health_check():
    """Check summarization service health."""
    return {
        "status": "healthy",
        "service": "Summarization",
        "models": [
            f"PhoBERT ({settings.phobert_model_name})",
            f"ViT5 ({settings.vit5_model_name})",
            "Position-based",
        ],
    }

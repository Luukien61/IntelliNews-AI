"""Summarization API endpoints."""
import logging

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from services.summarization.models import NewsSummarizationResponse
from services.summarization.service import summarization_service

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
        return await summarization_service.summarize_news(news_id, force, db)

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
    Get summaries for a news article.

    If not cached, fetches content from news-service and generates them.
    Returns 404 if the news item is not found in news-service.
    """
    try:
        return await summarization_service.summarize_news(news_id, False, db)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get/generate summaries: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get/generate summaries: {str(e)}"
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

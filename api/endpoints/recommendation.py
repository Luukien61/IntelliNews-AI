"""Recommendation API endpoints."""
import logging
from fastapi import APIRouter, HTTPException

from services.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    IndexArticleRequest,
    IndexBatchRequest,
    IndexResponse,
    recommendation_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendation", tags=["Recommendation"])


@router.post("/similar", response_model=RecommendationResponse)
async def get_similar_articles(request: RecommendationRequest):
    """
    Get similar news articles based on content similarity.
    
    Uses PhoBERT embeddings and cosine similarity to find articles
    with similar content to the given news_id.
    
    The source article must be indexed first (via /index or /index/batch).
    """
    try:
        logger.info(f"Recommendation request for news_id={request.news_id}")
        
        recommendations, is_cached = await recommendation_service.get_similar_articles(
            news_id=request.news_id,
            limit=request.limit,
            category_filter=request.category_filter
        )
        
        return RecommendationResponse(
            success=True,
            source_news_id=request.news_id,
            recommendations=recommendations,
            cached=is_cached,
            message=f"Found {len(recommendations)} similar articles"
        )
        
    except Exception as e:
        logger.error(f"Recommendation failed for news_id={request.news_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendations: {str(e)}"
        )


@router.post("/index", response_model=IndexResponse)
async def index_article(request: IndexArticleRequest):
    """
    Generate and store embedding for a single news article.
    
    Fetches the article content from the news-service backend,
    generates a PhoBERT embedding, and stores it in PostgreSQL.
    """
    try:
        logger.info(f"Index request for news_id={request.news_id}")
        
        indexed = await recommendation_service.index_article(request.news_id)
        
        return IndexResponse(
            success=True,
            indexed_count=1 if indexed else 0,
            skipped_count=0 if indexed else 1,
            message="Article indexed successfully" if indexed else "Article already indexed"
        )
        
    except Exception as e:
        logger.error(f"Indexing failed for news_id={request.news_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index article: {str(e)}"
        )


@router.post("/index/batch", response_model=IndexResponse)
async def index_articles_batch(request: IndexBatchRequest):
    """
    Generate and store embeddings for a batch of articles.
    
    Fetches articles from the news-service backend (paginated),
    generates PhoBERT embeddings for each, and stores them in PostgreSQL.
    Already-indexed articles are skipped.
    """
    try:
        logger.info(f"Batch index request: page={request.page}, size={request.size}, category={request.category}")
        
        indexed, skipped = await recommendation_service.index_articles_batch(
            page=request.page,
            size=request.size,
            category=request.category
        )
        
        return IndexResponse(
            success=True,
            indexed_count=indexed,
            skipped_count=skipped,
            message=f"Batch indexing complete: {indexed} indexed, {skipped} skipped"
        )
        
    except Exception as e:
        logger.error(f"Batch indexing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index articles: {str(e)}"
        )


@router.get("/stats")
async def get_stats():
    """Get embedding index statistics."""
    try:
        stats = recommendation_service.get_embedding_stats()
        return {
            "status": "healthy",
            "service": "Content-Based Recommendation",
            **stats
        }
    except Exception as e:
        logger.error(f"Stats retrieval failed: {str(e)}")
        return {
            "status": "error",
            "service": "Content-Based Recommendation",
            "error": str(e)
        }


@router.get("/health")
async def health_check():
    """Check recommendation service health."""
    return {
        "status": "healthy",
        "service": "Content-Based Recommendation",
        "model": "PhoBERT (vinai/phobert-base)"
    }

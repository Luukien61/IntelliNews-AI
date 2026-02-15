from pydantic import BaseModel, Field
from typing import List, Optional


class RecommendationRequest(BaseModel):
    """Request model for content-based news recommendation."""
    
    news_id: int = Field(..., description="News item ID to get similar articles for")
    limit: int = Field(default=10, ge=1, le=50, description="Number of recommendations to return")
    category_filter: Optional[str] = Field(
        default=None,
        description="Optional category filter (e.g., 'CONG_NGHE'). If set, only returns articles from that category."
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "news_id": 42,
                "limit": 10,
                "category_filter": None
            }
        }


class IndexArticleRequest(BaseModel):
    """Request model for indexing a single article for recommendation."""
    
    news_id: int = Field(..., description="News item ID to generate embedding for")


class IndexBatchRequest(BaseModel):
    """Request model for batch indexing articles."""
    
    page: int = Field(default=0, ge=0, description="Page number (0-indexed)")
    size: int = Field(default=50, ge=1, le=200, description="Number of articles per batch")
    category: Optional[str] = Field(
        default=None,
        description="Optional category to limit indexing (e.g., 'CONG_NGHE')"
    )


class RecommendedNewsItem(BaseModel):
    """Individual recommended news item."""
    
    news_id: int = Field(..., description="News article ID")
    title: str = Field(..., description="News article title")
    category: str = Field(..., description="News category")
    similarity_score: float = Field(..., description="Cosine similarity score (0-1)")


class RecommendationResponse(BaseModel):
    """Response model for news recommendation."""
    
    success: bool = Field(..., description="Whether recommendation was successful")
    source_news_id: int = Field(..., description="The news ID that recommendations are based on")
    recommendations: List[RecommendedNewsItem] = Field(
        default_factory=list,
        description="List of recommended news items sorted by similarity"
    )
    cached: bool = Field(default=False, description="Whether the result was served from cache")
    message: str = Field(default="", description="Additional message or error details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "source_news_id": 42,
                "recommendations": [
                    {"news_id": 101, "title": "Bài báo AI mới", "category": "CONG_NGHE", "similarity_score": 0.92}
                ],
                "cached": False,
                "message": "Recommendations generated successfully"
            }
        }


class IndexResponse(BaseModel):
    """Response model for indexing operations."""
    
    success: bool = Field(..., description="Whether indexing was successful")
    indexed_count: int = Field(default=0, description="Number of articles indexed")
    skipped_count: int = Field(default=0, description="Number of articles skipped (already indexed)")
    message: str = Field(default="", description="Additional message or error details")

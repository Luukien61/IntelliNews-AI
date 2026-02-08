from pydantic import BaseModel, Field
from typing import List


class RecommendationRequest(BaseModel):
    """Request model for news recommendation."""
    
    user_id: str = Field(..., description="User ID for personalized recommendations")
    limit: int = Field(default=10, ge=1, le=100, description="Number of recommendations to return")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "limit": 10
            }
        }


class NewsItem(BaseModel):
    """Individual news item in recommendation response."""
    
    id: str = Field(..., description="News article ID")
    title: str = Field(..., description="News article title")
    score: float = Field(..., description="Recommendation score")


class RecommendationResponse(BaseModel):
    """Response model for news recommendation."""
    
    success: bool = Field(..., description="Whether recommendation was successful")
    recommendations: List[NewsItem] = Field(default_factory=list, description="List of recommended news items")
    message: str = Field(default="", description="Additional message or error details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "recommendations": [
                    {"id": "news123", "title": "Sample news article", "score": 0.95}
                ],
                "message": "Recommendations generated successfully"
            }
        }

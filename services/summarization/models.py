"""Pydantic models for summarization API."""
from pydantic import BaseModel, Field
from typing import Optional


class NewsSummarizationResponse(BaseModel):
    """Response model for news summarization endpoint."""

    success: bool = Field(..., description="Whether summarization was successful")
    news_id: int = Field(..., description="ID of the news item")
    summary_short: Optional[str] = Field(
        default=None, description="Short abstractive summary (ViT5)"
    )
    summary_default: Optional[str] = Field(
        default=None, description="Default extractive summary (PhoBERT)"
    )
    cached: bool = Field(
        default=False, description="Whether results were served from cache"
    )
    message: str = Field(default="", description="Additional message or error details")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "news_id": 1,
                "summary_short": "Tóm tắt ngắn gọn bài viết...",
                "summary_default": "Câu 1 được chọn. Câu 3 được chọn. Câu 5 được chọn.",
                "cached": False,
                "message": "Summaries generated successfully",
            }
        }

from pydantic import BaseModel, Field
from typing import Optional


class SummarizationRequest(BaseModel):
    """Request model for text summarization."""
    
    text: str = Field(
        ...,
        description="Text to summarize",
        min_length=1,
        max_length=50000
    )
    max_length: Optional[int] = Field(
        default=150,
        ge=50,
        le=500,
        description="Maximum length of summary"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Long news article text to be summarized...",
                "max_length": 150
            }
        }


class SummarizationResponse(BaseModel):
    """Response model for text summarization."""
    
    success: bool = Field(..., description="Whether summarization was successful")
    summary: str = Field(default="", description="Generated summary")
    original_length: int = Field(..., description="Length of original text")
    summary_length: int = Field(..., description="Length of summary")
    message: str = Field(default="", description="Additional message or error details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "summary": "This is a summary of the news article...",
                "original_length": 1000,
                "summary_length": 150,
                "message": "Summary generated successfully"
            }
        }

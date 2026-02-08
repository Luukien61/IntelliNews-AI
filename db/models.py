"""SQLAlchemy models for IntelliNews AI Service."""
from sqlalchemy import Column, BigInteger, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .database import Base


class NewsAIResult(Base):
    """
    Model for storing AI processing results for news items.
    Includes TTS audio files and summaries.
    
    Attributes:
        id: Primary key
        news_id: Reference to news_items.id in news-service (unique)
        audio_files: JSONB array of audio file info
        summary_short: Short summary of the news
        summary_medium: Medium-length summary
        summary_default: Default/full summary
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    __tablename__ = "news_ai_results"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    news_id = Column(BigInteger, unique=True, nullable=False, index=True)
    
    # JSONB array storing audio file information
    # Format: [{"voice_id": "Doan", "description": "Giọng nam miền Bắc", "url": "...", "s3_key": "...", "presigned_url": "..."}]
    audio_files = Column(JSONB, nullable=False, default=[])
    
    # Summary fields (moved from news-service)
    summary_short = Column(Text, nullable=True)
    summary_medium = Column(Text, nullable=True)
    summary_default = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<NewsAIResult(id={self.id}, news_id={self.news_id}, audio_count={len(self.audio_files or [])})>"

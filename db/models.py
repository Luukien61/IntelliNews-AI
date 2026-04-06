"""SQLAlchemy models for IntelliNews AI Service."""
from sqlalchemy import Column, BigInteger, Integer, Float, Text, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

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


class NewsEmbedding(Base):
    """
    Model for storing news article embeddings for recommendation & clustering.
    Uses pgvector's native vector type for efficient similarity search.
    
    The embedding model is configured via EMBEDDING_MODEL_NAME env variable
    (default: bkai-foundation-models/vietnamese-bi-encoder).
    
    Attributes:
        id: Primary key
        news_id: Reference to news_items.id in news-service (unique)
        category: News category (cached for filtering)
        title: News title (cached for response)
        embedding: 768-dim embedding vector (pgvector vector type)
        created_at: Timestamp when embedding was generated
        updated_at: Timestamp when embedding was last updated
    """
    __tablename__ = "news_embeddings"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    news_id = Column(BigInteger, unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    title = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=False)  # pgvector native type
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    published_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<NewsEmbedding(id={self.id}, news_id={self.news_id}, category={self.category})>"


class TrendingCluster(Base):
    """
    Model for storing trending clusters information.
    
    Attributes:
        id: Primary key
        cluster_id: HDBSCAN cluster ID
        category: News category
        article_count: Number of articles in cluster
        trending_score: Calculated score based on recency, velocity, article count
        summary: Auto-generated summary of the cluster
        representative_ids: Array of representative news_id
        period_start: Start timestamp of the cluster window
        period_end: End timestamp of the cluster window
        created_at: Record creation time
    """
    __tablename__ = "trending_clusters"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    cluster_id = Column(Integer, nullable=False)
    category = Column(String(50), nullable=False)
    article_count = Column(Integer, nullable=False, default=0)
    trending_score = Column(Float, nullable=False, default=0.0)
    primary_rep_id = Column(BigInteger, nullable=True)  # Bài tiêu biểu để get summary
    
    from sqlalchemy.dialects.postgresql import ARRAY
    representative_ids = Column(ARRAY(BigInteger), nullable=True) # Tất cả news_id trong cụm
    
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    from sqlalchemy import UniqueConstraint, Index
    __table_args__ = (
        UniqueConstraint('cluster_id', 'category', name='trending_clusters_cluster_id_category_key'),
        Index('idx_trending_clusters_score', 'trending_score'),
        Index('idx_trending_clusters_category', 'category', 'trending_score'),
    )

    def __repr__(self):
        return f"<TrendingCluster(id={self.id}, cluster_id={self.cluster_id}, category={self.category}, score={self.trending_score})>"

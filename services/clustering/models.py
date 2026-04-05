"""Pydantic models for clustering API responses."""
from typing import Optional, List
from pydantic import BaseModel


class TrendingClusterItem(BaseModel):
    """Single trending cluster in API response."""
    cluster_id: int
    category: str
    article_count: int
    trending_score: float
    primary_rep_id: Optional[int] = None
    representative_ids: List[int] = []
    period_start: Optional[str] = None
    period_end: Optional[str] = None


class TrendingClusterResponse(BaseModel):
    """Response model for trending clusters endpoint."""
    success: bool = True
    clusters: List[TrendingClusterItem] = []
    total: int = 0
    message: str = ""

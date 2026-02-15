"""Recommendation service module."""
from .models import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendedNewsItem,
    IndexArticleRequest,
    IndexBatchRequest,
    IndexResponse
)
from .service import ContentRecommendationService, recommendation_service

__all__ = [
    "RecommendationRequest",
    "RecommendationResponse",
    "RecommendedNewsItem",
    "IndexArticleRequest",
    "IndexBatchRequest",
    "IndexResponse",
    "ContentRecommendationService",
    "recommendation_service",
]

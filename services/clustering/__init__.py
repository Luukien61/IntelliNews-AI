"""Clustering service module for trending news detection."""
from .service import ClusteringService, clustering_service
from .models import TrendingClusterResponse, TrendingClusterItem

__all__ = [
    "ClusteringService",
    "clustering_service",
    "TrendingClusterResponse",
    "TrendingClusterItem",
]

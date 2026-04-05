"""API endpoint for trending news clusters."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from services.clustering.service import clustering_service
from services.clustering.models import TrendingClusterResponse, TrendingClusterItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trending", tags=["trending"])


@router.get("", response_model=TrendingClusterResponse)
async def get_trending_clusters(
    category: Optional[str] = Query(None, description="Filter by category"),
    hours: float = Query(4.0, ge=1, le=48, description="Lookback window in hours"),
    limit: int = Query(10, ge=1, le=50, description="Max clusters to return"),
    db: Session = Depends(get_db),
):
    """
    Get trending news clusters.

    Returns top clusters sorted by trending_score within the specified
    time window. Each cluster includes a summary of the representative
    article and the list of article IDs.
    """
    try:
        if category:
            raw = clustering_service.get_trending_clusters(
                db=db, category=category, limit=limit
            )
        else:
            raw = clustering_service.get_top_trending(
                db=db, hours=hours, limit=limit
            )

        items = [TrendingClusterItem(**r) for r in raw]

        return TrendingClusterResponse(
            success=True,
            clusters=items,
            total=len(items),
            message=f"Found {len(items)} trending cluster(s)",
        )

    except Exception as e:
        logger.error(f"Error fetching trending clusters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=dict)
async def trigger_pipeline():
    """
    Manually trigger the clustering pipeline.
    
    Useful for development / testing. In production the pipeline
    runs automatically every 2 hours via the scheduler.
    """
    try:
        result = await clustering_service.run_pipeline()
        return result
    except Exception as e:
        logger.error(f"Manual pipeline run failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

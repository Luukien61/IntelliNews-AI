#!/usr/bin/env python3
"""
Script to manually cleanup old clusters from the trending_clusters table.
This removes clusters where period_end is older than the configured expiry hours.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from config import settings
from db.database import SessionLocal
from db.models import TrendingCluster

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_old_clusters(dry_run: bool = False):
    """
    Clean up expired clusters from the database.
    
    Args:
        dry_run: If True, only show what would be deleted without actually deleting
    """
    db = SessionLocal()
    try:
        expiry_cutoff = datetime.now(timezone.utc) - timedelta(
            hours=settings.clustering_expiry_hours
        )
        
        logger.info(f"Expiry cutoff: {expiry_cutoff.isoformat()}")
        logger.info(f"Clustering expiry hours: {settings.clustering_expiry_hours}")
        
        # Find clusters to delete
        old_clusters = db.query(TrendingCluster).filter(
            TrendingCluster.period_end < expiry_cutoff
        ).all()
        
        if not old_clusters:
            logger.info("No expired clusters found!")
            return
        
        logger.info(f"\nFound {len(old_clusters)} expired clusters:")
        for cluster in old_clusters:
            age_days = (datetime.now(timezone.utc) - cluster.period_end).days
            logger.info(
                f"  - ID={cluster.id}, cluster_id={cluster.cluster_id}, "
                f"category={cluster.category}, "
                f"period_end={cluster.period_end.isoformat()}, "
                f"age={age_days} days"
            )
        
        if dry_run:
            logger.info("\n[DRY RUN] No clusters were deleted. Run with dry_run=False to actually delete.")
        else:
            result = db.query(TrendingCluster).filter(
                TrendingCluster.period_end < expiry_cutoff
            ).delete(synchronize_session=False)
            db.commit()
            logger.info(f"\n✅ Successfully deleted {result} expired clusters!")
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    # Check if user passed --force flag
    dry_run = "--force" not in sys.argv
    
    if dry_run:
        print("=" * 70)
        print("DRY RUN MODE - No data will be deleted")
        print("Add --force flag to actually delete expired clusters")
        print("=" * 70)
        print()
    
    cleanup_old_clusters(dry_run=dry_run)
    
    if dry_run:
        print()
        print("=" * 70)
        print("To actually delete these clusters, run:")
        print("  python scripts/cleanup_old_clusters.py --force")
        print("=" * 70)


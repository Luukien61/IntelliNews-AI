"""
APScheduler-based scheduler for the clustering pipeline.

Runs `clustering_service.run_pipeline()` every 2 hours
so that trending data stays fresh.
"""
import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Interval in seconds (2 hours)
CLUSTERING_INTERVAL_SECONDS = 2 * 60 * 60

# Initial delay before first run (60 seconds after startup — let models warm up)
INITIAL_DELAY_SECONDS = 60


class ClusteringScheduler:
    """Lightweight async scheduler that runs the clustering pipeline periodically."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        """Start the background scheduling loop."""
        if self._running:
            logger.warning("Clustering scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            f"Clustering scheduler started "
            f"(interval={CLUSTERING_INTERVAL_SECONDS}s, "
            f"initial_delay={INITIAL_DELAY_SECONDS}s)"
        )

    def stop(self):
        """Stop the background scheduling loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("Clustering scheduler stopped")

    async def _loop(self):
        """Internal loop: wait → run pipeline → repeat."""
        # Initial delay
        logger.info(
            f"Clustering scheduler: waiting {INITIAL_DELAY_SECONDS}s before first run"
        )
        await asyncio.sleep(INITIAL_DELAY_SECONDS)

        while self._running:
            try:
                await self._run_once()
            except Exception as exc:
                logger.error(
                    f"Clustering scheduler task error: {exc}", exc_info=True
                )

            # Sleep until next interval
            if self._running:
                logger.info(
                    f"Next clustering run in {CLUSTERING_INTERVAL_SECONDS}s"
                )
                await asyncio.sleep(CLUSTERING_INTERVAL_SECONDS)

    async def _run_once(self):
        """Execute a single pipeline run."""
        from services.clustering.service import clustering_service

        logger.info(
            f"[Scheduler] Running clustering pipeline at "
            f"{datetime.now(timezone.utc).isoformat()}"
        )
        result = await clustering_service.run_pipeline()
        logger.info(f"[Scheduler] Pipeline result: {result}")


# Global singleton
clustering_scheduler = ClusteringScheduler()

"""
APScheduler-based scheduler for the clustering pipeline.

Runs `clustering_service.run_pipeline()` every 2 hours
so that trending data stays fresh.
"""
import asyncio
import logging
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger(__name__)

# Read interval from settings (default 2 h); override via CLUSTERING_SCHEDULER_INTERVAL_SECONDS env var
CLUSTERING_INTERVAL_SECONDS = settings.clustering_scheduler_interval_seconds

# Initial delay before first run (60 seconds after startup — let models warm up)
INITIAL_DELAY_SECONDS = 600


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
        """
        Internal loop: wait → run pipeline → repeat.
        
        Only runs clustering when AI processor has no active tasks
        (no summarization, embedding, or TTS in progress).
        """
        # Initial delay
        logger.info(
            f"Clustering scheduler: waiting {INITIAL_DELAY_SECONDS}s before first run"
        )
        await asyncio.sleep(INITIAL_DELAY_SECONDS)

        while self._running:
            try:
                from services.ai_processor_service import ai_processor
                
                # Wait until no active AI tasks (summarization, embedding, TTS)
                if ai_processor.active_tasks > 0:
                    logger.info(
                        f"Clustering delayed: AI service has {ai_processor.active_tasks} active tasks. "
                        f"Will retry in 60s..."
                    )
                    await asyncio.sleep(60)
                    continue
                
                # All clear - run clustering
                logger.info("No active AI tasks detected. Starting clustering pipeline...")
                await self._run_once()
                
            except Exception as exc:
                logger.error(
                    f"Clustering scheduler task error: {exc}", exc_info=True
                )

            # Sleep until next interval
            if self._running:
                logger.info(
                    f"Next clustering check in {CLUSTERING_INTERVAL_SECONDS}s"
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

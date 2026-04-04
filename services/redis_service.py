import logging

from config import settings

logger = logging.getLogger(__name__)

class RedisService:
    """
    Centralized Redis connection manager.
    """
    def __init__(self):
        self._redis = None

    async def get_redis(self):
        """Get or create Redis connection (lazy initialization)."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    settings.redis_url,
                    decode_responses=False
                )
                # Test connection
                await self._redis.ping()
                logger.info(f"Redis connected: {settings.redis_url}")
            except Exception as e:
                logger.warning(f"Redis not available: {e}")
                self._redis = None
        return self._redis

redis_service = RedisService()

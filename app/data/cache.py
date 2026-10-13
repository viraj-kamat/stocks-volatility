import redis
import json
import logging
from typing import Optional, List
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, host: str = settings.redis_host, port: int = settings.redis_port):
        self.host = host
        self.port = port
        self.redis_client = self._connect()

    def _connect(self) -> redis.Redis:
        try:
            client = redis.Redis(
                host=self.host,
                port=self.port,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            client.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
            return client
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def cache_latest_prices(self, prices_dict: dict, ttl_minutes: int = 30):
        """
        Cache latest prices for all stocks.
        """
        try:
            key = "latest_prices"
            ttl_seconds = ttl_minutes * 60

            self.redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(prices_dict, default=str)
            )
            logger.info(f"Cached latest prices for {len(prices_dict)} stocks")
        except Exception as e:
            logger.error(f"Error caching latest prices: {e}")

    def get_cached_latest_prices(self) -> Optional[dict]:
        """
        Retrieve cached latest prices.
        """
        try:
            cached = self.redis_client.get("latest_prices")
            if cached is None:
                return None
            return json.loads(cached)
        except Exception as e:
            logger.error(f"Error retrieving cached latest prices: {e}")
            return None

    def clear_cache(self, pattern: str = "*"):
        """
        Clear cache entries matching a pattern.
        """
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries matching pattern: {pattern}")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def close(self):
        """Close Redis connection."""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Closed Redis connection")


cache = RedisCache()

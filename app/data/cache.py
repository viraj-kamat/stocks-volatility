import redis
import json
import logging
from typing import Optional, List
from datetime import datetime
import pandas as pd
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

    def cache_stock_data(self, symbol: str, data: pd.DataFrame, ttl_hours: int = 6):
        """
        Cache historical stock data as JSON.
        """
        try:
            # Convert DataFrame to JSON-serializable format
            data_dict = data.to_dict(orient='records')
            key = f"stock:{symbol}:data"

            # Store in Redis with TTL
            ttl_seconds = ttl_hours * 3600
            self.redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(data_dict, default=str)
            )
            logger.info(f"Cached data for {symbol} ({len(data_dict)} records, TTL: {ttl_hours}h)")
        except Exception as e:
            logger.error(f"Error caching data for {symbol}: {e}")

    def get_cached_stock_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Retrieve cached stock data.
        """
        try:
            key = f"stock:{symbol}:data"
            cached_data = self.redis_client.get(key)

            if cached_data is None:
                return None

            data_dict = json.loads(cached_data)
            df = pd.DataFrame(data_dict)

            # Convert date strings back to datetime
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])

            logger.info(f"Retrieved cached data for {symbol} ({len(df)} records)")
            return df
        except Exception as e:
            logger.error(f"Error retrieving cached data for {symbol}: {e}")
            return None

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

    def cache_analysis_result(self, symbol: str, alerts: List[dict], ttl_hours: int = 24):
        """
        Cache analysis results.
        """
        try:
            key = f"analysis:{symbol}:alerts"
            ttl_seconds = ttl_hours * 3600

            self.redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(alerts, default=str)
            )
            logger.info(f"Cached analysis results for {symbol} ({len(alerts)} alerts)")
        except Exception as e:
            logger.error(f"Error caching analysis results for {symbol}: {e}")

    def get_cached_analysis_result(self, symbol: str) -> Optional[List[dict]]:
        """
        Retrieve cached analysis results.
        """
        try:
            key = f"analysis:{symbol}:alerts"
            cached = self.redis_client.get(key)
            if cached is None:
                return None
            return json.loads(cached)
        except Exception as e:
            logger.error(f"Error retrieving cached analysis results for {symbol}: {e}")
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

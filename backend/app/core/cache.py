import json
import pickle
from typing import Any, Optional, Union
import redis.asyncio as aioredis
import redis
from datetime import timedelta
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis cache service for application data."""
    
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self._async_redis: Optional[aioredis.Redis] = None
        self._sync_redis: Optional[redis.Redis] = None
        
    async def get_async_redis(self) -> aioredis.Redis:
        """Get async Redis connection."""
        if self._async_redis is None:
            self._async_redis = aioredis.from_url(
                self.redis_url, 
                encoding="utf-8", 
                decode_responses=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
        return self._async_redis
        
    def get_sync_redis(self) -> redis.Redis:
        """Get sync Redis connection."""
        if self._sync_redis is None:
            self._sync_redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
        return self._sync_redis
        
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[Union[int, timedelta]] = None,
        serialize_method: str = "json"
    ) -> bool:
        """Set a value in cache."""
        try:
            redis_client = await self.get_async_redis()
            
            # Serialize the value
            if serialize_method == "json":
                serialized_value = json.dumps(value, default=str)
            elif serialize_method == "pickle":
                serialized_value = pickle.dumps(value)
            else:
                serialized_value = str(value)
                
            # Set the value
            return await redis_client.set(key, serialized_value, ex=expire)
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
            
    async def get(
        self, 
        key: str, 
        deserialize_method: str = "json"
    ) -> Optional[Any]:
        """Get a value from cache."""
        try:
            redis_client = await self.get_async_redis()
            value = await redis_client.get(key)
            
            if value is None:
                return None
                
            # Deserialize the value
            if deserialize_method == "json":
                return json.loads(value)
            elif deserialize_method == "pickle":
                return pickle.loads(value)
            else:
                return value
                
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
            
    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        try:
            redis_client = await self.get_async_redis()
            return await redis_client.delete(key) > 0
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
            
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        try:
            redis_client = await self.get_async_redis()
            return await redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
            
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern."""
        try:
            redis_client = await self.get_async_redis()
            keys = await redis_client.keys(pattern)
            if keys:
                return await redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear pattern error for pattern {pattern}: {e}")
            return 0
            
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a numeric value in cache."""
        try:
            redis_client = await self.get_async_redis()
            return await redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return 0
            
    async def set_hash(self, key: str, mapping: dict, expire: Optional[int] = None) -> bool:
        """Set a hash in cache."""
        try:
            redis_client = await self.get_async_redis()
            await redis_client.hset(key, mapping=mapping)
            if expire:
                await redis_client.expire(key, expire)
            return True
        except Exception as e:
            logger.error(f"Cache set hash error for key {key}: {e}")
            return False
            
    async def get_hash(self, key: str) -> Optional[dict]:
        """Get a hash from cache."""
        try:
            redis_client = await self.get_async_redis()
            return await redis_client.hgetall(key)
        except Exception as e:
            logger.error(f"Cache get hash error for key {key}: {e}")
            return None
            
    async def health_check(self) -> bool:
        """Check if Redis is accessible."""
        try:
            redis_client = await self.get_async_redis()
            await redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Cache key generators
class CacheKeys:
    """Cache key generators for different data types."""
    
    @staticmethod
    def player_predictions(gameweek: int, season: str) -> str:
        """Cache key for player predictions."""
        return f"predictions:{season}:gw{gameweek}"
        
    @staticmethod
    def player_prediction(player_id: int, gameweek: int, season: str) -> str:
        """Cache key for single player prediction."""
        return f"prediction:{season}:gw{gameweek}:player{player_id}"
        
    @staticmethod
    def players_data(filters_hash: str) -> str:
        """Cache key for players list with filters."""
        return f"players:{filters_hash}"
        
    @staticmethod
    def player_detail(player_id: int) -> str:
        """Cache key for player detail."""
        return f"player:{player_id}"
        
    @staticmethod
    def team_data(team_id: int) -> str:
        """Cache key for team data."""
        return f"team:{team_id}"
        
    @staticmethod
    def optimization_result(constraints_hash: str, gameweek: int) -> str:
        """Cache key for optimization results."""
        return f"optimization:{gameweek}:{constraints_hash}"
        
    @staticmethod
    def fixture_analysis(gameweeks: int) -> str:
        """Cache key for fixture analysis."""
        return f"fixtures:analysis:{gameweeks}gw"
        
    @staticmethod
    def top_performers(gameweek: int, position: Optional[int] = None) -> str:
        """Cache key for top performers."""
        pos_suffix = f":pos{position}" if position else ""
        return f"top_performers:gw{gameweek}{pos_suffix}"
        
    @staticmethod
    def captain_options(gameweek: int) -> str:
        """Cache key for captain options."""
        return f"captain_options:gw{gameweek}"
        
    @staticmethod
    def differentials(gameweek: int, max_ownership: float) -> str:
        """Cache key for differential players."""
        return f"differentials:gw{gameweek}:own{max_ownership}"


# Cache decorators
def cache_result(
    key_func,
    expire: int = 3600,
    serialize_method: str = "json"
):
    """Decorator to cache function results."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_func(*args, **kwargs)
            
            # Try to get from cache
            cache_service = CacheService()
            cached_result = await cache_service.get(
                cache_key, 
                deserialize_method=serialize_method
            )
            
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
                
            # Execute function and cache result
            result = await func(*args, **kwargs)
            
            if result is not None:
                await cache_service.set(
                    cache_key, 
                    result, 
                    expire=expire,
                    serialize_method=serialize_method
                )
                logger.debug(f"Cache set for key: {cache_key}")
                
            return result
            
        return wrapper
    return decorator


# Global cache service instance
cache_service = CacheService()
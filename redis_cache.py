"""
Redis-powered caching system for ultra-fast lead operations
This module provides Redis caching for maximum performance in production
"""

import redis
import json
import pickle
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis-powered caching system for ultra-fast operations"""
    
    def __init__(self, redis_url=None, default_ttl=300):
        """
        Initialize Redis cache
        
        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379)
            default_ttl: Default time-to-live in seconds (5 minutes)
        """
        self.default_ttl = default_ttl
        
        try:
            # Try to connect to Redis
            if redis_url:
                self.redis = redis.from_url(redis_url, decode_responses=False)
            else:
                # Default to localhost for development
                self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=False)
            
            # Test connection
            self.redis.ping()
            self.available = True
            logger.info("✅ Redis cache initialized successfully")
            
        except Exception as e:
            logger.warning(f"⚠️ Redis not available: {str(e)}. Falling back to in-memory cache.")
            self.available = False
            self.redis = None
    
    def _serialize(self, data: Any) -> bytes:
        """Serialize data for Redis storage"""
        try:
            return pickle.dumps(data)
        except Exception:
            return json.dumps(data, default=str).encode('utf-8')
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize data from Redis storage"""
        try:
            return pickle.loads(data)
        except Exception:
            return json.loads(data.decode('utf-8'))
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.available or not self.redis:
            return None
        
        try:
            data = self.redis.get(key)
            if data:
                logger.info(f"🎯 Cache HIT for key: {key}")
                return self._deserialize(data)
            else:
                logger.info(f"❌ Cache MISS for key: {key}")
                return None
        except Exception as e:
            logger.error(f"Error getting from Redis cache: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with TTL"""
        if not self.available or not self.redis:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            serialized_data = self._serialize(value)
            result = self.redis.setex(key, ttl, serialized_data)
            logger.info(f"💾 Cache SET for key: {key} (TTL: {ttl}s)")
            return result
        except Exception as e:
            logger.error(f"Error setting Redis cache: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.available or not self.redis:
            return False
        
        try:
            result = self.redis.delete(key)
            logger.info(f"🗑️ Cache DELETE for key: {key}")
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting from Redis cache: {str(e)}")
            return False
    
    def clear(self) -> bool:
        """Clear all cache"""
        if not self.available or not self.redis:
            return False
        
        try:
            self.redis.flushdb()
            logger.info("🧹 Cache CLEARED")
            return True
        except Exception as e:
            logger.error(f"Error clearing Redis cache: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.available or not self.redis:
            return {"available": False, "error": "Redis not available"}
        
        try:
            info = self.redis.info()
            return {
                "available": True,
                "connected_clients": info.get('connected_clients', 0),
                "used_memory_human": info.get('used_memory_human', '0B'),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0),
                "total_commands_processed": info.get('total_commands_processed', 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except Exception as e:
            return {"available": True, "error": str(e)}
    
    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate"""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0
    
    def set_lead_data(self, uid: str, data: Dict[str, Any], ttl: int = 300) -> bool:
        """Cache lead data with optimized key"""
        key = f"lead:{uid}"
        return self.set(key, data, ttl)
    
    def get_lead_data(self, uid: str) -> Optional[Dict[str, Any]]:
        """Get cached lead data"""
        key = f"lead:{uid}"
        return self.get(key)
    
    def invalidate_lead(self, uid: str) -> bool:
        """Invalidate lead cache"""
        key = f"lead:{uid}"
        return self.delete(key)
    
    def set_dashboard_data(self, user_type: str, user_name: str, filters: Dict, data: Dict[str, Any], ttl: int = 180) -> bool:
        """Cache dashboard data"""
        filter_hash = hash(str(sorted(filters.items()))) if filters else 0
        key = f"dashboard:{user_type}:{user_name}:{filter_hash}"
        return self.set(key, data, ttl)
    
    def get_dashboard_data(self, user_type: str, user_name: str, filters: Dict) -> Optional[Dict[str, Any]]:
        """Get cached dashboard data"""
        filter_hash = hash(str(sorted(filters.items()))) if filters else 0
        key = f"dashboard:{user_type}:{user_name}:{filter_hash}"
        return self.get(key)
    
    def invalidate_user_dashboard(self, user_type: str, user_name: str) -> bool:
        """Invalidate all dashboard cache for a user"""
        if not self.available or not self.redis:
            return False
        
        try:
            pattern = f"dashboard:{user_type}:{user_name}:*"
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
                logger.info(f"🗑️ Invalidated {len(keys)} dashboard cache keys for {user_type}:{user_name}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating dashboard cache: {str(e)}")
            return False

# Global Redis cache instance
redis_cache = RedisCache()

def get_redis_cache() -> RedisCache:
    """Get the global Redis cache instance"""
    return redis_cache 
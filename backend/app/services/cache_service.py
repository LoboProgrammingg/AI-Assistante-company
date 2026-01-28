"""
Serviço de cache usando Redis - Compatibilidade.

Este arquivo mantém compatibilidade com imports existentes.
A implementação real está em app/core/cache/
"""

from app.core.cache.redis_client import RedisClient, get_redis_client
from app.core.cache.manager import CacheManager, get_cache

CacheService = RedisClient

cache_service = get_redis_client()

__all__ = ["CacheService", "cache_service", "CacheManager", "get_cache"]

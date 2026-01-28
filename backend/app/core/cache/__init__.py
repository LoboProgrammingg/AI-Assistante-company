"""
Sistema de Cache Unificado para IRIS.

Arquitetura enterprise com:
- Redis como backend principal
- Fallback automático para memória local
- TTL dinâmico por tipo de dados
- Namespaces para isolamento
- Estatísticas e monitoramento
"""

from app.core.cache.manager import CacheManager, get_cache
from app.core.cache.memory import MemoryCache
from app.core.cache.redis_client import RedisClient
from app.core.cache.ai_context import AIContextCache, get_ai_cache

__all__ = [
    "CacheManager",
    "get_cache",
    "MemoryCache",
    "RedisClient",
    "AIContextCache",
    "get_ai_cache",
]

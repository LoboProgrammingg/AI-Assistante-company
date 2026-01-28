"""
Gerenciador de cache unificado para IRIS - Compatibilidade.

Este arquivo mantém compatibilidade com imports existentes.
A implementação real está em app/core/cache/
"""

from app.core.cache.manager import CacheManager, CacheNamespace, CacheTTL, get_cache
from app.core.cache.memory import MemoryCache
from app.core.cache.ai_context import AIContextCache, get_ai_cache

__all__ = [
    "CacheManager",
    "CacheNamespace",
    "CacheTTL",
    "get_cache",
    "MemoryCache",
    "AIContextCache",
    "get_ai_cache",
]

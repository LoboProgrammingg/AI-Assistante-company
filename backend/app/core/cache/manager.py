"""
Gerenciador de Cache Unificado para IRIS.

Arquitetura enterprise com:
- Redis como backend principal
- Fallback automático para memória local
- Namespaces para isolamento de dados
- TTL dinâmico por tipo de dado
- Write-through para consistência
"""

import hashlib
import logging
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

from app.core.cache.memory import MemoryCache
from app.core.cache.redis_client import RedisClient, get_redis_client

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheNamespace(str, Enum):
    """Namespaces de cache com TTLs padrão."""
    
    AI_CONTEXT = "ai:context"
    AI_CONVERSATION = "ai:conversation"
    AI_CLASSIFICATION = "ai:classification"
    AI_EMBEDDING = "ai:embedding"
    AI_FACTS = "ai:facts"
    AI_BEHAVIOR = "ai:behavior"
    
    USER_DATA = "user:data"
    USER_SESSION = "user:session"
    USER_PREFERENCES = "user:preferences"
    
    FINANCE = "finance"
    RATE_LIMIT = "rate_limit"
    
    LLM_RESPONSE = "llm:response"
    SEARCH_RESULT = "search:result"
    
    DEFAULT = "default"


class CacheTTL:
    """TTLs padrão por namespace (em segundos)."""
    
    TTLS: Dict[str, int] = {
        CacheNamespace.AI_CONTEXT: 180,
        CacheNamespace.AI_CONVERSATION: 120,
        CacheNamespace.AI_CLASSIFICATION: 300,
        CacheNamespace.AI_EMBEDDING: 3600,
        CacheNamespace.AI_FACTS: 1800,
        CacheNamespace.AI_BEHAVIOR: 900,
        CacheNamespace.USER_DATA: 300,
        CacheNamespace.USER_SESSION: 14400,
        CacheNamespace.USER_PREFERENCES: 1800,
        CacheNamespace.FINANCE: 300,
        CacheNamespace.RATE_LIMIT: 60,
        CacheNamespace.LLM_RESPONSE: 180,
        CacheNamespace.SEARCH_RESULT: 600,
        CacheNamespace.DEFAULT: 300,
    }
    
    @classmethod
    def get(cls, namespace: str) -> int:
        """Retorna TTL para namespace."""
        return cls.TTLS.get(namespace, cls.TTLS[CacheNamespace.DEFAULT])


class CacheManager:
    """
    Gerenciador de cache unificado com Redis + fallback memória.
    
    Features:
    - Singleton thread-safe
    - Fallback automático Redis -> Memória
    - Namespaces para organização
    - TTL dinâmico por tipo
    - Write-through: escreve em ambos backends
    - Estatísticas consolidadas
    """
    
    _instance: Optional["CacheManager"] = None
    
    PREFIX: str = "iris"
    
    def __new__(cls) -> "CacheManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._redis = get_redis_client()
        self._memory = MemoryCache(max_size=3000, default_ttl=300)
        
        backend = "Redis" if self._redis.is_available else "Memória"
        logger.info(f"[CACHE] ✓ Manager inicializado (backend: {backend})")
        
        self._initialized = True
    
    @property
    def redis_available(self) -> bool:
        """Verifica se Redis está disponível."""
        return self._redis.is_available
    
    def _build_key(self, namespace: str, key: str) -> str:
        """Constrói chave completa com prefixo e namespace."""
        return f"{self.PREFIX}:{namespace}:{key}"
    
    def _get_ttl(self, namespace: str, custom_ttl: Optional[int] = None) -> int:
        """Retorna TTL para namespace."""
        return custom_ttl or CacheTTL.get(namespace)
    
    def get(
        self,
        namespace: str,
        key: str,
        default: Optional[T] = None
    ) -> Optional[T]:
        """
        Busca valor no cache.
        
        Estratégia: Redis primeiro, fallback memória.
        
        Args:
            namespace: Namespace do cache
            key: Chave dentro do namespace
            default: Valor padrão se não encontrado
            
        Returns:
            Valor cacheado ou default
        """
        full_key = self._build_key(namespace, key)
        
        if self._redis.is_available:
            value = self._redis.get(full_key)
            if value is not None:
                return value
        
        value = self._memory.get(full_key)
        if value is not None:
            return value
        
        return default
    
    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Armazena valor no cache.
        
        Estratégia write-through: escreve em Redis e memória.
        
        Args:
            namespace: Namespace do cache
            key: Chave dentro do namespace
            value: Valor a armazenar
            ttl: TTL em segundos (opcional, usa padrão do namespace)
            
        Returns:
            True se sucesso em pelo menos um backend
        """
        full_key = self._build_key(namespace, key)
        ttl = self._get_ttl(namespace, ttl)
        
        redis_ok = False
        if self._redis.is_available:
            redis_ok = self._redis.set(full_key, value, ttl)
        
        self._memory.set(full_key, value, ttl, namespace)
        
        return redis_ok or True
    
    def delete(self, namespace: str, key: str) -> bool:
        """
        Remove valor do cache.
        
        Args:
            namespace: Namespace do cache
            key: Chave a remover
            
        Returns:
            True se removido de pelo menos um backend
        """
        full_key = self._build_key(namespace, key)
        
        redis_ok = False
        if self._redis.is_available:
            redis_ok = self._redis.delete(full_key)
        
        memory_ok = self._memory.delete(full_key)
        
        return redis_ok or memory_ok
    
    def delete_pattern(self, namespace: str, pattern: str = "*") -> int:
        """
        Remove todas as chaves que correspondem ao padrão.
        
        Args:
            namespace: Namespace do cache
            pattern: Padrão dentro do namespace
            
        Returns:
            Número de chaves removidas
        """
        full_pattern = self._build_key(namespace, pattern)
        
        count = 0
        
        if self._redis.is_available:
            count += self._redis.delete_pattern(full_pattern)
        
        count += self._memory.delete_pattern(f"{self.PREFIX}:{namespace}:")
        
        return count
    
    def invalidate_user(self, user_id: int) -> int:
        """
        Invalida todo o cache de um usuário.
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Número de chaves removidas
        """
        count = 0
        
        namespaces = [
            CacheNamespace.AI_CONTEXT,
            CacheNamespace.AI_CONVERSATION,
            CacheNamespace.AI_FACTS,
            CacheNamespace.AI_BEHAVIOR,
            CacheNamespace.USER_DATA,
            CacheNamespace.USER_PREFERENCES,
            CacheNamespace.FINANCE,
        ]
        
        for ns in namespaces:
            count += self.delete_pattern(ns, f"*:{user_id}:*")
            count += self.delete_pattern(ns, f"{user_id}:*")
            count += self.delete_pattern(ns, f"*:{user_id}")
            self.delete(ns, str(user_id))
        
        logger.debug(f"[CACHE] Invalidado cache do user {user_id} ({count} keys)")
        return count
    
    def get_or_set(
        self,
        namespace: str,
        key: str,
        factory: Callable[[], T],
        ttl: Optional[int] = None
    ) -> T:
        """
        Busca valor ou gera e armazena se não existir.
        
        Args:
            namespace: Namespace do cache
            key: Chave dentro do namespace
            factory: Função para gerar valor
            ttl: TTL em segundos (opcional)
            
        Returns:
            Valor do cache ou gerado
        """
        value = self.get(namespace, key)
        
        if value is not None:
            return value
        
        value = factory()
        
        if value is not None:
            self.set(namespace, key, value, ttl)
        
        return value
    
    async def get_or_set_async(
        self,
        namespace: str,
        key: str,
        factory: Callable[[], T],
        ttl: Optional[int] = None
    ) -> T:
        """
        Versão async do get_or_set.
        
        Args:
            namespace: Namespace do cache
            key: Chave dentro do namespace
            factory: Função async para gerar valor
            ttl: TTL em segundos (opcional)
            
        Returns:
            Valor do cache ou gerado
        """
        value = self.get(namespace, key)
        
        if value is not None:
            return value
        
        value = await factory()
        
        if value is not None:
            self.set(namespace, key, value, ttl)
        
        return value
    
    def exists(self, namespace: str, key: str) -> bool:
        """Verifica se chave existe."""
        full_key = self._build_key(namespace, key)
        
        if self._redis.is_available and self._redis.exists(full_key):
            return True
        
        return self._memory.exists(full_key)
    
    def get_ttl(self, namespace: str, key: str) -> Optional[int]:
        """Retorna TTL restante de uma chave."""
        full_key = self._build_key(namespace, key)
        
        if self._redis.is_available:
            ttl = self._redis.get_ttl(full_key)
            if ttl is not None:
                return ttl
        
        return self._memory.get_ttl(full_key)
    
    def touch(self, namespace: str, key: str, ttl: Optional[int] = None) -> bool:
        """
        Atualiza TTL de uma chave existente.
        
        Args:
            namespace: Namespace do cache
            key: Chave a atualizar
            ttl: Novo TTL (opcional, usa padrão do namespace)
            
        Returns:
            True se atualizado
        """
        full_key = self._build_key(namespace, key)
        ttl = self._get_ttl(namespace, ttl)
        
        if self._redis.is_available:
            return self._redis.expire(full_key, ttl)
        
        value = self._memory.get(full_key)
        if value is not None:
            self._memory.set(full_key, value, ttl, namespace)
            return True
        
        return False
    
    def clear_namespace(self, namespace: str) -> int:
        """
        Limpa todo o namespace.
        
        Args:
            namespace: Namespace a limpar
            
        Returns:
            Número de chaves removidas
        """
        return self.delete_pattern(namespace)
    
    def hash_key(self, *parts: str) -> str:
        """
        Gera hash MD5 para usar como chave.
        
        Útil para cachear por conteúdo.
        
        Args:
            *parts: Partes para compor o hash
            
        Returns:
            Hash MD5 hexadecimal
        """
        content = ":".join(str(p) for p in parts)
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas consolidadas do cache."""
        redis_info = self._redis.get_info() if self._redis.is_available else None
        memory_stats = self._memory.get_stats()
        
        return {
            "primary_backend": "redis" if self._redis.is_available else "memory",
            "redis": redis_info,
            "memory": memory_stats,
        }


_cache_manager: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Retorna instância singleton do CacheManager."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager

"""
Cache em memória local com LRU eviction e TTL.

Usado como fallback quando Redis não está disponível.
Thread-safe para uso em ambiente async.
"""

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Entrada de cache com metadados."""
    
    value: T
    expires_at: float
    created_at: float = field(default_factory=time.time)
    hits: int = 0
    namespace: str = "default"


@dataclass
class CacheStats:
    """Estatísticas do cache."""
    
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired: int = 0
    
    @property
    def total_requests(self) -> int:
        return self.hits + self.misses
    
    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expired": self.expired,
            "total_requests": self.total_requests,
            "hit_rate": f"{self.hit_rate:.1f}%",
        }


class MemoryCache:
    """
    Cache em memória com LRU eviction e TTL.
    
    Features:
    - Thread-safe com RLock
    - LRU eviction automático
    - TTL por entrada
    - Limpeza lazy de expirados
    - Estatísticas de uso
    """
    
    DEFAULT_MAX_SIZE: int = 2000
    DEFAULT_TTL: int = 300
    CLEANUP_THRESHOLD: int = 100
    
    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        default_ttl: int = DEFAULT_TTL
    ):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = RLock()
        self._stats = CacheStats()
        self._operation_count = 0
    
    def _cleanup_expired(self) -> int:
        """Remove entradas expiradas. Retorna quantidade removida."""
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry.expires_at
        ]
        
        for key in expired_keys:
            del self._cache[key]
            self._stats.expired += 1
        
        return len(expired_keys)
    
    def _maybe_cleanup(self) -> None:
        """Executa limpeza periódica de expirados."""
        self._operation_count += 1
        if self._operation_count >= self.CLEANUP_THRESHOLD:
            self._operation_count = 0
            self._cleanup_expired()
    
    def _evict_lru(self) -> None:
        """Remove entradas mais antigas até ter espaço."""
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
            self._stats.evictions += 1
    
    def get(self, key: str) -> Optional[Any]:
        """
        Busca valor no cache.
        
        Args:
            key: Chave do cache
            
        Returns:
            Valor ou None se não encontrado/expirado
        """
        with self._lock:
            self._maybe_cleanup()
            
            if key not in self._cache:
                self._stats.misses += 1
                return None
            
            entry = self._cache[key]
            
            if time.time() > entry.expires_at:
                del self._cache[key]
                self._stats.expired += 1
                self._stats.misses += 1
                return None
            
            entry.hits += 1
            self._cache.move_to_end(key)
            self._stats.hits += 1
            
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "default"
    ) -> None:
        """
        Armazena valor no cache.
        
        Args:
            key: Chave do cache
            value: Valor a armazenar
            ttl: TTL em segundos (opcional)
            namespace: Namespace para organização
        """
        ttl = ttl or self._default_ttl
        
        with self._lock:
            self._evict_lru()
            
            now = time.time()
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=now + ttl,
                created_at=now,
                namespace=namespace
            )
    
    def delete(self, key: str) -> bool:
        """
        Remove valor do cache.
        
        Args:
            key: Chave a remover
            
        Returns:
            True se removido, False se não existia
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Remove todas as chaves que começam com o padrão.
        
        Args:
            pattern: Prefixo das chaves a remover
            
        Returns:
            Número de chaves removidas
        """
        with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if key.startswith(pattern)
            ]
            
            for key in keys_to_delete:
                del self._cache[key]
            
            return len(keys_to_delete)
    
    def clear(self) -> None:
        """Limpa todo o cache."""
        with self._lock:
            self._cache.clear()
            self._stats = CacheStats()
    
    def clear_namespace(self, namespace: str) -> int:
        """
        Limpa todas as entradas de um namespace.
        
        Args:
            namespace: Namespace a limpar
            
        Returns:
            Número de entradas removidas
        """
        with self._lock:
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if entry.namespace == namespace
            ]
            
            for key in keys_to_delete:
                del self._cache[key]
            
            return len(keys_to_delete)
    
    def exists(self, key: str) -> bool:
        """Verifica se chave existe e não está expirada."""
        with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if time.time() > entry.expires_at:
                del self._cache[key]
                return False
            
            return True
    
    def get_ttl(self, key: str) -> Optional[int]:
        """Retorna TTL restante de uma chave em segundos."""
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            remaining = entry.expires_at - time.time()
            
            if remaining <= 0:
                del self._cache[key]
                return None
            
            return int(remaining)
    
    def size(self) -> int:
        """Retorna número de entradas no cache."""
        return len(self._cache)
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        with self._lock:
            return {
                "backend": "memory",
                "size": len(self._cache),
                "max_size": self._max_size,
                "default_ttl": self._default_ttl,
                **self._stats.to_dict()
            }
    
    def get_keys(self, pattern: Optional[str] = None) -> list:
        """
        Retorna lista de chaves.
        
        Args:
            pattern: Filtro opcional (prefixo)
            
        Returns:
            Lista de chaves
        """
        with self._lock:
            if pattern:
                return [k for k in self._cache.keys() if k.startswith(pattern)]
            return list(self._cache.keys())

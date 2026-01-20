"""
Gerenciador de cache unificado para IRIS.
Abstrai Redis e fallback para memória local.
"""

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Generic, Optional, TypeVar


logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Entrada de cache com TTL."""

    value: T
    expires_at: float
    created_at: float
    hits: int = 0


class MemoryCache:
    """Cache em memória com LRU eviction e TTL."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get(self, key: str) -> Optional[Any]:
        """Busca valor no cache."""
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None

            entry = self._cache[key]

            # Verificar expiração
            if time.time() > entry.expires_at:
                del self._cache[key]
                self._stats["misses"] += 1
                return None

            # Atualizar hits e mover para o final (LRU)
            entry.hits += 1
            self._cache.move_to_end(key)
            self._stats["hits"] += 1

            return entry.value

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Armazena valor no cache."""
        ttl = ttl or self.default_ttl

        with self._lock:
            # Evict se necessário
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1

            now = time.time()
            self._cache[key] = CacheEntry(value=value, expires_at=now + ttl, created_at=now)

    def delete(self, key: str) -> bool:
        """Remove valor do cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Limpa todo o cache."""
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "hit_rate": f"{hit_rate:.1f}%",
        }


class CacheManager:
    """
    Gerenciador de cache unificado.

    Features:
    - Fallback automático: Redis -> Memória
    - Namespaces para organização
    - TTL configurável por namespace
    - Estatísticas de uso
    """

    _instance: Optional["CacheManager"] = None

    # TTLs padrão por namespace (segundos)
    DEFAULT_TTLS = {
        "classification": 300,  # 5 minutos
        "embedding": 3600,  # 1 hora
        "user_context": 60,  # 1 minuto
        "llm_response": 120,  # 2 minutos
        "rate_limit": 60,  # 1 minuto
        "default": 300,  # 5 minutos
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._memory_cache = MemoryCache()
        self._redis_available = False
        self._redis_client = None

        # Tentar conectar ao Redis
        self._init_redis()
        self._initialized = True

        backend = "Redis" if self._redis_available else "Memória"
        logger.info(f"CacheManager inicializado (backend: {backend})")

    def _init_redis(self) -> None:
        """Tenta inicializar conexão Redis."""
        try:
            from app.services.cache_service import cache_service

            if cache_service.is_available:
                self._redis_client = cache_service
                self._redis_available = True
                logger.info("Redis disponível para cache")
        except Exception as e:
            logger.info(f"Redis não disponível, usando memória: {e}")

    def _get_full_key(self, namespace: str, key: str) -> str:
        """Gera chave completa com namespace."""
        return f"iris:{namespace}:{key}"

    def _get_ttl(self, namespace: str) -> int:
        """Retorna TTL para namespace."""
        return self.DEFAULT_TTLS.get(namespace, self.DEFAULT_TTLS["default"])

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Busca valor no cache."""
        full_key = self._get_full_key(namespace, key)

        # Tentar Redis primeiro
        if self._redis_available:
            try:
                value = self._redis_client.get(full_key)
                if value is not None:
                    return value
            except Exception as e:
                logger.warning(f"Erro ao buscar no Redis: {e}")

        # Fallback para memória
        return self._memory_cache.get(full_key)

    def set(self, namespace: str, key: str, value: Any, ttl: int = None) -> None:
        """Armazena valor no cache."""
        full_key = self._get_full_key(namespace, key)
        ttl = ttl or self._get_ttl(namespace)

        # Tentar Redis primeiro
        if self._redis_available:
            try:
                self._redis_client.set(full_key, value, ttl_seconds=ttl)
                return
            except Exception as e:
                logger.warning(f"Erro ao salvar no Redis: {e}")

        # Fallback para memória
        self._memory_cache.set(full_key, value, ttl)

    def delete(self, namespace: str, key: str) -> bool:
        """Remove valor do cache."""
        full_key = self._get_full_key(namespace, key)

        deleted = False

        if self._redis_available:
            try:
                self._redis_client.delete(full_key)
                deleted = True
            except Exception:
                pass

        deleted = self._memory_cache.delete(full_key) or deleted
        return deleted

    def clear_namespace(self, namespace: str) -> int:
        """Limpa todos os valores de um namespace."""
        # Só funciona bem com memória local
        # Redis precisaria de SCAN que é mais complexo
        count = 0
        prefix = self._get_full_key(namespace, "")

        keys_to_delete = [k for k in self._memory_cache._cache.keys() if k.startswith(prefix)]

        for key in keys_to_delete:
            self._memory_cache.delete(key)
            count += 1

        return count

    def get_or_set(self, namespace: str, key: str, factory_fn, ttl: int = None) -> Any:
        """
        Busca valor ou gera e armazena se não existir.

        Args:
            namespace: Namespace do cache
            key: Chave
            factory_fn: Função para gerar valor se não existir
            ttl: TTL opcional

        Returns:
            Valor do cache ou gerado
        """
        value = self.get(namespace, key)

        if value is not None:
            return value

        # Gerar valor
        value = factory_fn()

        if value is not None:
            self.set(namespace, key, value, ttl)

        return value

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        stats = {
            "backend": "redis" if self._redis_available else "memory",
            "memory_stats": self._memory_cache.get_stats(),
        }

        return stats


# Instância global
_cache_manager: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Retorna instância global do cache manager."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager

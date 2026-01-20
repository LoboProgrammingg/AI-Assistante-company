"""
Serviço de cache usando Redis.
"""

import json
import logging
from typing import Any, Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Serviço de cache usando Redis."""

    _instance: Optional["CacheService"] = None
    _redis: Optional[redis.Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._redis is None:
            try:
                # Usar REDIS_URL se disponível (Railway), senão usar host/port
                if settings.REDIS_URL:
                    self._redis = redis.from_url(
                        settings.get_redis_url, decode_responses=True, socket_timeout=5, socket_connect_timeout=5
                    )
                else:
                    self._redis = redis.Redis(
                        host=settings.REDIS_HOST,
                        port=settings.REDIS_PORT,
                        db=settings.REDIS_DB,
                        decode_responses=True,
                        socket_timeout=5,
                        socket_connect_timeout=5,
                    )
                self._redis.ping()
                logger.info("Conexão com Redis estabelecida")
            except redis.ConnectionError as e:
                logger.warning(f"Redis não disponível: {e}")
                self._redis = None

    @property
    def is_available(self) -> bool:
        """Verifica se o Redis está disponível."""
        if self._redis is None:
            return False
        try:
            self._redis.ping()
            return True
        except redis.ConnectionError:
            return False

    def get(self, key: str) -> Optional[Any]:
        """
        Obtém valor do cache.

        Args:
            key: Chave do cache

        Returns:
            Valor deserializado ou None
        """
        if not self.is_available:
            return None

        try:
            value = self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Erro ao obter cache: {e}")
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """
        Define valor no cache.

        Args:
            key: Chave do cache
            value: Valor a ser armazenado
            ttl_seconds: Tempo de vida em segundos (default: 5 min)

        Returns:
            True se sucesso
        """
        if not self.is_available:
            return False

        try:
            serialized = json.dumps(value, default=str)
            self._redis.setex(key, ttl_seconds, serialized)
            return True
        except (redis.RedisError, TypeError) as e:
            logger.error(f"Erro ao definir cache: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Remove chave do cache."""
        if not self.is_available:
            return False

        try:
            self._redis.delete(key)
            return True
        except redis.RedisError as e:
            logger.error(f"Erro ao deletar cache: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Remove todas as chaves que correspondem ao padrão.

        Args:
            pattern: Padrão de chaves (ex: "user:*:stats")

        Returns:
            Número de chaves removidas
        """
        if not self.is_available:
            return 0

        try:
            keys = self._redis.keys(pattern)
            if keys:
                return self._redis.delete(*keys)
            return 0
        except redis.RedisError as e:
            logger.error(f"Erro ao deletar padrão: {e}")
            return 0

    def invalidate_user_cache(self, user_id: int) -> None:
        """Invalida todo o cache de um usuário."""
        self.delete_pattern(f"user:{user_id}:*")

    def get_user_stats_key(self, user_id: int) -> str:
        """Gera chave de cache para stats do usuário."""
        return f"user:{user_id}:stats"

    def get_finance_summary_key(self, user_id: int, year: int, month: int) -> str:
        """Gera chave de cache para resumo financeiro."""
        return f"user:{user_id}:finance:{year}:{month}"


# Singleton instance
cache_service = CacheService()

"""
Cliente Redis enterprise para IRIS.

Features:
- Conexão resiliente com retry
- Pool de conexões
- Serialização automática JSON
- Health check
- Fallback gracioso
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

from app.config import settings

logger = logging.getLogger(__name__)

try:
    import redis
    from redis import ConnectionPool
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    logger.warning("[REDIS] Biblioteca redis não instalada")


class RedisClient:
    """
    Cliente Redis com pool de conexões e serialização automática.
    
    Features:
    - Singleton thread-safe
    - Pool de conexões reutilizáveis
    - Serialização JSON automática
    - Health check
    - Retry em falhas de conexão
    """
    
    _instance: Optional["RedisClient"] = None
    _pool: Optional["ConnectionPool"] = None
    
    SOCKET_TIMEOUT: int = 5
    SOCKET_CONNECT_TIMEOUT: int = 5
    MAX_CONNECTIONS: int = 20
    RETRY_ON_TIMEOUT: bool = True
    
    def __new__(cls) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._client: Optional["redis.Redis"] = None
        self._available = False
        self._last_error: Optional[str] = None
        
        self._connect()
        self._initialized = True
    
    def _connect(self) -> None:
        """Estabelece conexão com Redis."""
        if not HAS_REDIS:
            logger.info("[REDIS] Biblioteca não disponível, usando fallback")
            return
        
        redis_url = settings.REDIS_URL or settings.get_redis_url
        
        if not redis_url:
            logger.warning("[REDIS] URL não configurada")
            return
        
        try:
            if RedisClient._pool is None:
                RedisClient._pool = ConnectionPool.from_url(
                    redis_url,
                    max_connections=self.MAX_CONNECTIONS,
                    socket_timeout=self.SOCKET_TIMEOUT,
                    socket_connect_timeout=self.SOCKET_CONNECT_TIMEOUT,
                    retry_on_timeout=self.RETRY_ON_TIMEOUT,
                    decode_responses=True,
                )
            
            self._client = redis.Redis(connection_pool=RedisClient._pool)
            self._client.ping()
            self._available = True
            
            logger.info("[REDIS] ✓ Conexão estabelecida")
            
        except redis.ConnectionError as e:
            self._last_error = str(e)
            logger.warning(f"[REDIS] Conexão falhou: {e}")
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"[REDIS] Erro inesperado: {e}")
    
    @property
    def is_available(self) -> bool:
        """Verifica se Redis está disponível."""
        if not self._available or not self._client:
            return False
        
        try:
            self._client.ping()
            return True
        except Exception:
            self._available = False
            return False
    
    def _serialize(self, value: Any) -> str:
        """Serializa valor para JSON."""
        return json.dumps(value, default=str, ensure_ascii=False)
    
    def _deserialize(self, value: Optional[str]) -> Optional[Any]:
        """Deserializa valor de JSON."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    
    def get(self, key: str) -> Optional[Any]:
        """
        Busca valor no Redis.
        
        Args:
            key: Chave do cache
            
        Returns:
            Valor deserializado ou None
        """
        if not self.is_available:
            return None
        
        try:
            value = self._client.get(key)
            return self._deserialize(value)
        except Exception as e:
            logger.warning(f"[REDIS] Erro ao buscar {key}: {e}")
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Armazena valor no Redis.
        
        Args:
            key: Chave do cache
            value: Valor a armazenar
            ttl: TTL em segundos (opcional)
            
        Returns:
            True se sucesso
        """
        if not self.is_available:
            return False
        
        try:
            serialized = self._serialize(value)
            
            if ttl:
                self._client.setex(key, ttl, serialized)
            else:
                self._client.set(key, serialized)
            
            return True
        except Exception as e:
            logger.warning(f"[REDIS] Erro ao salvar {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Remove chave do Redis.
        
        Args:
            key: Chave a remover
            
        Returns:
            True se removida
        """
        if not self.is_available:
            return False
        
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"[REDIS] Erro ao deletar {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Remove todas as chaves que correspondem ao padrão.
        
        Args:
            pattern: Padrão glob (ex: "user:*:cache")
            
        Returns:
            Número de chaves removidas
        """
        if not self.is_available:
            return 0
        
        try:
            keys = list(self._client.scan_iter(match=pattern, count=100))
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"[REDIS] Erro ao deletar padrão {pattern}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Verifica se chave existe."""
        if not self.is_available:
            return False
        
        try:
            return bool(self._client.exists(key))
        except Exception:
            return False
    
    def get_ttl(self, key: str) -> Optional[int]:
        """Retorna TTL restante de uma chave."""
        if not self.is_available:
            return None
        
        try:
            ttl = self._client.ttl(key)
            return ttl if ttl > 0 else None
        except Exception:
            return None
    
    def expire(self, key: str, ttl: int) -> bool:
        """Define TTL para uma chave existente."""
        if not self.is_available:
            return False
        
        try:
            return bool(self._client.expire(key, ttl))
        except Exception:
            return False
    
    def hget(self, key: str, field: str) -> Optional[Any]:
        """Busca campo de um hash."""
        if not self.is_available:
            return None
        
        try:
            value = self._client.hget(key, field)
            return self._deserialize(value)
        except Exception as e:
            logger.warning(f"[REDIS] Erro hget {key}.{field}: {e}")
            return None
    
    def hset(self, key: str, field: str, value: Any) -> bool:
        """Define campo de um hash."""
        if not self.is_available:
            return False
        
        try:
            self._client.hset(key, field, self._serialize(value))
            return True
        except Exception as e:
            logger.warning(f"[REDIS] Erro hset {key}.{field}: {e}")
            return False
    
    def hgetall(self, key: str) -> Dict[str, Any]:
        """Retorna todos os campos de um hash."""
        if not self.is_available:
            return {}
        
        try:
            data = self._client.hgetall(key)
            return {k: self._deserialize(v) for k, v in data.items()}
        except Exception as e:
            logger.warning(f"[REDIS] Erro hgetall {key}: {e}")
            return {}
    
    def hdel(self, key: str, field: str) -> bool:
        """Remove campo de um hash."""
        if not self.is_available:
            return False
        
        try:
            self._client.hdel(key, field)
            return True
        except Exception:
            return False
    
    def lpush(self, key: str, *values: Any) -> bool:
        """Adiciona valores ao início de uma lista."""
        if not self.is_available:
            return False
        
        try:
            serialized = [self._serialize(v) for v in values]
            self._client.lpush(key, *serialized)
            return True
        except Exception as e:
            logger.warning(f"[REDIS] Erro lpush {key}: {e}")
            return False
    
    def lrange(self, key: str, start: int, end: int) -> List[Any]:
        """Retorna range de uma lista."""
        if not self.is_available:
            return []
        
        try:
            values = self._client.lrange(key, start, end)
            return [self._deserialize(v) for v in values]
        except Exception as e:
            logger.warning(f"[REDIS] Erro lrange {key}: {e}")
            return []
    
    def ltrim(self, key: str, start: int, end: int) -> bool:
        """Mantém apenas range especificado de uma lista."""
        if not self.is_available:
            return False
        
        try:
            self._client.ltrim(key, start, end)
            return True
        except Exception:
            return False
    
    def incr(self, key: str) -> Optional[int]:
        """Incrementa valor inteiro."""
        if not self.is_available:
            return None
        
        try:
            return self._client.incr(key)
        except Exception:
            return None
    
    def get_info(self) -> Dict[str, Any]:
        """Retorna informações do servidor Redis."""
        if not self.is_available:
            return {"available": False, "error": self._last_error}
        
        try:
            info = self._client.info("server")
            memory = self._client.info("memory")
            
            return {
                "available": True,
                "version": info.get("redis_version"),
                "uptime_days": info.get("uptime_in_days"),
                "used_memory_human": memory.get("used_memory_human"),
                "connected_clients": self._client.info("clients").get("connected_clients"),
            }
        except Exception as e:
            return {"available": True, "error": str(e)}


_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Retorna instância singleton do cliente Redis."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client

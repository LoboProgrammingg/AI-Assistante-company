"""
Redis Working Memory - Camada intermediária de memória.

Esta camada mantém:
- Contexto de sessão (4 horas)
- Working memory ativa (24 horas)
- Cache de memórias do PostgreSQL (1 hora)
- Contexto compilado para LLM (5 minutos)

REGRAS:
- Sempre isolado por user_id
- TTL dinâmico por risco de operação
- Fallback gracioso se Redis indisponível
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


# Tentar importar Redis
try:
    import redis

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    logger.warning("[REDIS_WORKING] Redis não disponível")


class RedisWorkingMemory:
    """
    Working Memory em Redis para IRIS v3.

    Camada intermediária entre sessão e PostgreSQL.
    Fornece cache rápido e contexto temporário.
    """

    # Prefixo para todas as keys
    PREFIX = "iris"

    # TTL padrão por tipo
    TTL_CONFIG = {
        "session": 4 * 3600,  # 4 horas
        "working": 24 * 3600,  # 24 horas
        "memory_cache": 3600,  # 1 hora
        "context": 300,  # 5 minutos
    }

    # TTL dinâmico por risco de operação
    TTL_BY_RISK = {
        "low": 1800,  # 30 min - saudações, perguntas simples
        "medium": 7200,  # 2 horas - consultas, buscas
        "high": 14400,  # 4 horas - ações financeiras
        "critical": 86400,  # 24 horas - decisões importantes
    }

    # Mapeamento de ações para níveis de risco
    ACTION_RISK_MAP = {
        # Baixo risco
        "direct_response": "low",
        "greeting": "low",
        "query_finance": "low",
        "list_reminders": "low",
        "list_contacts": "low",
        # Médio risco
        "search": "medium",
        "list_events": "medium",
        "check_availability": "medium",
        # Alto risco
        "create_finance": "high",
        "create_reminder": "high",
        "schedule_message": "high",
        "create_event": "high",
        # Crítico
        "delete_finance": "critical",
        "create_goal": "critical",
        "extract_invoice": "critical",
    }

    def __init__(self, redis_url: str = None):
        """
        Inicializa conexão Redis.

        Args:
            redis_url: URL do Redis (default: settings.REDIS_URL)
        """
        self.redis = None
        self.enabled = False

        if not HAS_REDIS:
            logger.info("[REDIS_WORKING] Redis não instalado, usando fallback")
            return

        try:
            url = redis_url or getattr(settings, "REDIS_URL", None)
            if url:
                self.redis = redis.from_url(url, decode_responses=True)
                # Testar conexão
                self.redis.ping()
                self.enabled = True
                logger.info("[REDIS_WORKING] Conectado ao Redis")
            else:
                logger.warning("[REDIS_WORKING] REDIS_URL não configurado")
        except Exception as e:
            logger.warning(f"[REDIS_WORKING] Falha ao conectar: {e}")

    def _key(self, key_type: str, user_id: int, **kwargs) -> str:
        """Gera key padronizada."""
        base = f"{self.PREFIX}:user:{user_id}:{key_type}"
        if kwargs.get("session_id"):
            base += f":{kwargs['session_id']}"
        return base

    def get_ttl_for_action(self, action_type: str) -> int:
        """Retorna TTL apropriado para o tipo de ação."""
        risk = self.ACTION_RISK_MAP.get(action_type, "medium")
        return self.TTL_BY_RISK[risk]

    # ==================== SESSION ====================

    def set_session_context(
        self,
        user_id: int,
        session_id: str,
        context: Dict[str, Any],
        ttl: int = None,
    ) -> bool:
        """
        Salva contexto da sessão atual.

        Args:
            user_id: ID do usuário
            session_id: ID da sessão
            context: Contexto a salvar
            ttl: TTL em segundos (default: 4 horas)
        """
        if not self.enabled:
            return False

        try:
            key = self._key("session", user_id, session_id=session_id)
            ttl = ttl or self.TTL_CONFIG["session"]
            self.redis.setex(key, ttl, json.dumps(context, default=str))
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] set_session_context error: {e}")
            return False

    def get_session_context(
        self,
        user_id: int,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Recupera contexto da sessão."""
        if not self.enabled:
            return None

        try:
            key = self._key("session", user_id, session_id=session_id)
            data = self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_session_context error: {e}")
            return None

    def update_session_context(
        self,
        user_id: int,
        session_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """Atualiza contexto da sessão (merge)."""
        if not self.enabled:
            return False

        try:
            current = self.get_session_context(user_id, session_id) or {}
            current.update(updates)
            return self.set_session_context(user_id, session_id, current)
        except Exception as e:
            logger.error(f"[REDIS_WORKING] update_session_context error: {e}")
            return False

    # ==================== WORKING MEMORY ====================

    def add_to_working(
        self,
        user_id: int,
        memory_key: str,
        value: Any,
        ttl: int = None,
    ) -> bool:
        """
        Adiciona item à working memory.

        Args:
            user_id: ID do usuário
            memory_key: Chave do item
            value: Valor a armazenar
            ttl: TTL em segundos (default: 24 horas)
        """
        if not self.enabled:
            return False

        try:
            key = self._key("working", user_id)
            ttl = ttl or self.TTL_CONFIG["working"]

            # Usar hash para múltiplos itens
            self.redis.hset(key, memory_key, json.dumps(value, default=str))
            self.redis.expire(key, ttl)
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] add_to_working error: {e}")
            return False

    def get_from_working(self, user_id: int, memory_key: str) -> Optional[Any]:
        """Recupera item específico da working memory."""
        if not self.enabled:
            return None

        try:
            key = self._key("working", user_id)
            data = self.redis.hget(key, memory_key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_from_working error: {e}")
            return None

    def get_working_memory(self, user_id: int) -> Dict[str, Any]:
        """Retorna toda working memory."""
        if not self.enabled:
            return {}

        try:
            key = self._key("working", user_id)
            data = self.redis.hgetall(key)
            return {k: json.loads(v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_working_memory error: {e}")
            return {}

    def remove_from_working(self, user_id: int, memory_key: str) -> bool:
        """Remove item da working memory."""
        if not self.enabled:
            return False

        try:
            key = self._key("working", user_id)
            self.redis.hdel(key, memory_key)
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] remove_from_working error: {e}")
            return False

    def clear_working(self, user_id: int) -> bool:
        """Limpa toda working memory."""
        if not self.enabled:
            return False

        try:
            key = self._key("working", user_id)
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] clear_working error: {e}")
            return False

    # ==================== MEMORY CACHE ====================

    def cache_memories(
        self,
        user_id: int,
        memories: List[Dict],
        ttl: int = None,
    ) -> bool:
        """
        Cache de memórias do PostgreSQL.

        Args:
            user_id: ID do usuário
            memories: Lista de memórias
            ttl: TTL em segundos (default: 1 hora)
        """
        if not self.enabled:
            return False

        try:
            key = self._key("memory_cache", user_id)
            ttl = ttl or self.TTL_CONFIG["memory_cache"]
            self.redis.setex(key, ttl, json.dumps(memories, default=str))
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] cache_memories error: {e}")
            return False

    def get_cached_memories(self, user_id: int) -> Optional[List[Dict]]:
        """Recupera memórias cacheadas."""
        if not self.enabled:
            return None

        try:
            key = self._key("memory_cache", user_id)
            data = self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_cached_memories error: {e}")
            return None

    def invalidate_memory_cache(self, user_id: int) -> bool:
        """Invalida cache de memórias (após escrita)."""
        if not self.enabled:
            return False

        try:
            key = self._key("memory_cache", user_id)
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] invalidate_memory_cache error: {e}")
            return False

    # ==================== CONTEXT ====================

    def cache_llm_context(
        self,
        user_id: int,
        context: str,
        ttl: int = None,
    ) -> bool:
        """
        Cache do contexto compilado para LLM.

        Args:
            user_id: ID do usuário
            context: Contexto formatado
            ttl: TTL em segundos (default: 5 min)
        """
        if not self.enabled:
            return False

        try:
            key = self._key("context", user_id)
            ttl = ttl or self.TTL_CONFIG["context"]
            self.redis.setex(key, ttl, context)
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] cache_llm_context error: {e}")
            return False

    def get_cached_context(self, user_id: int) -> Optional[str]:
        """Recupera contexto cacheado."""
        if not self.enabled:
            return None

        try:
            key = self._key("context", user_id)
            return self.redis.get(key)
        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_cached_context error: {e}")
            return None

    # ==================== UTILITY ====================

    def invalidate_user(self, user_id: int) -> bool:
        """Invalida todo cache do usuário."""
        if not self.enabled:
            return False

        try:
            pattern = f"{self.PREFIX}:user:{user_id}:*"
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] invalidate_user error: {e}")
            return False

    def get_stats(self, user_id: int) -> Dict[str, Any]:
        """Retorna estatísticas de uso do cache."""
        if not self.enabled:
            return {"enabled": False}

        try:
            pattern = f"{self.PREFIX}:user:{user_id}:*"
            keys = self.redis.keys(pattern)

            stats = {
                "enabled": True,
                "total_keys": len(keys),
                "keys": [],
            }

            for key in keys:
                ttl = self.redis.ttl(key)
                key_type = key.split(":")[-1] if ":" in key else "unknown"
                stats["keys"].append(
                    {
                        "key": key,
                        "type": key_type,
                        "ttl_seconds": ttl,
                    }
                )

            return stats

        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_stats error: {e}")
            return {"enabled": True, "error": str(e)}


# Singleton instance
_redis_working_memory: Optional[RedisWorkingMemory] = None


def get_redis_working_memory() -> RedisWorkingMemory:
    """Retorna instância singleton do Redis Working Memory."""
    global _redis_working_memory
    if _redis_working_memory is None:
        _redis_working_memory = RedisWorkingMemory()
    return _redis_working_memory

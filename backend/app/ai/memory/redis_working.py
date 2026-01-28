"""
Redis Working Memory - Camada intermediária de memória.

MIGRADO para usar o sistema de cache unificado (app.core.cache).

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

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.cache import get_cache, get_ai_cache, CacheManager, AIContextCache

logger = logging.getLogger(__name__)


class RedisWorkingMemory:
    """
    Working Memory em Redis para IRIS v3.

    Usa o sistema de cache unificado (CacheManager + AIContextCache).
    Fornece cache rápido e contexto temporário.
    """

    TTL_CONFIG = {
        "session": 4 * 3600,
        "working": 24 * 3600,
        "memory_cache": 3600,
        "context": 300,
    }

    TTL_BY_RISK = {
        "low": 1800,
        "medium": 7200,
        "high": 14400,
        "critical": 86400,
    }

    ACTION_RISK_MAP = {
        "direct_response": "low",
        "greeting": "low",
        "query_finance": "low",
        "list_reminders": "low",
        "list_contacts": "low",
        "search": "medium",
        "list_events": "medium",
        "check_availability": "medium",
        "create_finance": "high",
        "create_reminder": "high",
        "schedule_message": "high",
        "create_event": "high",
        "delete_finance": "critical",
        "create_goal": "critical",
        "extract_invoice": "critical",
    }

    def __init__(self, redis_url: str = None):
        """Inicializa usando sistema de cache unificado."""
        self._cache: CacheManager = get_cache()
        self._ai_cache: AIContextCache = get_ai_cache()
        self.enabled = self._cache.redis_available
        
        if self.enabled:
            logger.info("[REDIS_WORKING] ✓ Usando cache unificado (Redis)")
        else:
            logger.info("[REDIS_WORKING] Usando cache unificado (Memória)")

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
        """Salva contexto da sessão atual."""
        try:
            self._ai_cache.set_session_context(user_id, session_id, context)
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
        try:
            return self._ai_cache.get_session_context(user_id, session_id)
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
        try:
            self._ai_cache.update_session_context(user_id, session_id, updates)
            return True
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
        """Adiciona item à working memory."""
        try:
            self._ai_cache.update_working_memory(user_id, memory_key, value)
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] add_to_working error: {e}")
            return False

    def get_from_working(self, user_id: int, memory_key: str) -> Optional[Any]:
        """Recupera item específico da working memory."""
        try:
            memory = self._ai_cache.get_working_memory(user_id)
            return memory.get(memory_key)
        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_from_working error: {e}")
            return None

    def get_working_memory(self, user_id: int) -> Dict[str, Any]:
        """Retorna toda working memory."""
        try:
            return self._ai_cache.get_working_memory(user_id)
        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_working_memory error: {e}")
            return {}

    def remove_from_working(self, user_id: int, memory_key: str) -> bool:
        """Remove item da working memory."""
        try:
            memory = self._ai_cache.get_working_memory(user_id)
            if memory_key in memory:
                del memory[memory_key]
                self._ai_cache.set_working_memory(user_id, memory)
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] remove_from_working error: {e}")
            return False

    def clear_working(self, user_id: int) -> bool:
        """Limpa toda working memory."""
        try:
            self._ai_cache.set_working_memory(user_id, {})
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
        """Cache de memórias do PostgreSQL."""
        try:
            self._ai_cache.set_learned_facts(user_id, {"memories": memories})
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] cache_memories error: {e}")
            return False

    def get_cached_memories(self, user_id: int) -> Optional[List[Dict]]:
        """Recupera memórias cacheadas."""
        try:
            data = self._ai_cache.get_learned_facts(user_id)
            return data.get("memories") if data else None
        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_cached_memories error: {e}")
            return None

    def invalidate_memory_cache(self, user_id: int) -> bool:
        """Invalida cache de memórias (após escrita)."""
        try:
            self._ai_cache.invalidate_facts(user_id)
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
        """Cache do contexto compilado para LLM."""
        try:
            self._ai_cache.set_full_context(user_id, {"compiled_context": context})
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] cache_llm_context error: {e}")
            return False

    def get_cached_context(self, user_id: int) -> Optional[str]:
        """Recupera contexto cacheado."""
        try:
            data = self._ai_cache.get_full_context(user_id)
            return data.get("compiled_context") if data else None
        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_cached_context error: {e}")
            return None

    # ==================== UTILITY ====================

    def invalidate_user(self, user_id: int) -> bool:
        """Invalida todo cache do usuário."""
        try:
            self._ai_cache.invalidate_user(user_id)
            return True
        except Exception as e:
            logger.error(f"[REDIS_WORKING] invalidate_user error: {e}")
            return False

    def get_stats(self, user_id: int) -> Dict[str, Any]:
        """Retorna estatísticas de uso do cache."""
        try:
            return {
                "enabled": self.enabled,
                "backend": "redis" if self._cache.redis_available else "memory",
                "cache_stats": self._ai_cache.get_stats(),
            }
        except Exception as e:
            logger.error(f"[REDIS_WORKING] get_stats error: {e}")
            return {"enabled": self.enabled, "error": str(e)}


# Singleton instance
_redis_working_memory: Optional[RedisWorkingMemory] = None


def get_redis_working_memory() -> RedisWorkingMemory:
    """Retorna instância singleton do Redis Working Memory."""
    global _redis_working_memory
    if _redis_working_memory is None:
        _redis_working_memory = RedisWorkingMemory()
    return _redis_working_memory

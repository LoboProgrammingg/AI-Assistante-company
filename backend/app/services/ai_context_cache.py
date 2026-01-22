"""
Cache Redis específico para contexto da IA.

Este serviço cacheia todas as informações relevantes para a IA,
garantindo respostas rápidas e contexto persistente entre requests.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.cache_manager import get_cache

logger = logging.getLogger(__name__)


class AIContextCache:
    """
    Cache especializado para contexto da IA IRIS.
    
    Cacheia:
    - Contexto completo do usuário (finanças, lembretes, etc)
    - Histórico de conversa
    - Fatos aprendidos
    - Preferências
    - Classificações de intenção
    - Embeddings de busca
    """

    # TTLs em segundos
    TTL_USER_CONTEXT = 120      # 2 minutos - dados mudam frequentemente
    TTL_CONVERSATION = 60      # 1 minuto - conversa ativa
    TTL_FACTS = 3600           # 1 hora - fatos aprendidos mudam pouco
    TTL_PREFERENCES = 1800     # 30 minutos
    TTL_CLASSIFICATION = 300   # 5 minutos - cache de classificação de intenção
    TTL_EMBEDDING = 3600       # 1 hora - embeddings de busca
    TTL_FINANCE_SUMMARY = 300  # 5 minutos - resumo financeiro

    def __init__(self):
        self._cache = get_cache()

    def _key(self, namespace: str, user_id: int, extra: str = "") -> str:
        """Gera chave de cache."""
        if extra:
            return f"ai:{namespace}:{user_id}:{extra}"
        return f"ai:{namespace}:{user_id}"

    # ==================== CONTEXTO COMPLETO ====================

    def get_full_context(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Busca contexto completo cacheado."""
        return self._cache.get("ai_context", f"full:{user_id}")

    def set_full_context(self, user_id: int, context: Dict[str, Any]) -> None:
        """Cacheia contexto completo."""
        self._cache.set("ai_context", f"full:{user_id}", context, self.TTL_USER_CONTEXT)
        logger.debug(f"[CACHE] Contexto completo cacheado para user {user_id}")

    def invalidate_full_context(self, user_id: int) -> None:
        """Invalida contexto completo (após ações que modificam dados)."""
        self._cache.delete("ai_context", f"full:{user_id}")
        logger.debug(f"[CACHE] Contexto invalidado para user {user_id}")

    # ==================== HISTÓRICO DE CONVERSA ====================

    def get_conversation(self, user_id: int, limit: int = 20) -> Optional[List[Dict]]:
        """Busca histórico de conversa cacheado."""
        return self._cache.get("ai_conversation", f"{user_id}:{limit}")

    def set_conversation(self, user_id: int, messages: List[Dict], limit: int = 20) -> None:
        """Cacheia histórico de conversa."""
        self._cache.set("ai_conversation", f"{user_id}:{limit}", messages, self.TTL_CONVERSATION)

    def invalidate_conversation(self, user_id: int) -> None:
        """Invalida conversa (após nova mensagem)."""
        # Invalida todas as variações de limit
        for limit in [10, 15, 20, 30]:
            self._cache.delete("ai_conversation", f"{user_id}:{limit}")

    # ==================== FATOS APRENDIDOS ====================

    def get_learned_facts(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Busca fatos aprendidos cacheados."""
        return self._cache.get("ai_facts", str(user_id))

    def set_learned_facts(self, user_id: int, facts: Dict[str, Any]) -> None:
        """Cacheia fatos aprendidos."""
        self._cache.set("ai_facts", str(user_id), facts, self.TTL_FACTS)

    def invalidate_facts(self, user_id: int) -> None:
        """Invalida fatos (após aprender algo novo)."""
        self._cache.delete("ai_facts", str(user_id))

    # ==================== PREFERÊNCIAS ====================

    def get_preferences(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Busca preferências cacheadas."""
        return self._cache.get("ai_preferences", str(user_id))

    def set_preferences(self, user_id: int, prefs: Dict[str, Any]) -> None:
        """Cacheia preferências."""
        self._cache.set("ai_preferences", str(user_id), prefs, self.TTL_PREFERENCES)

    # ==================== CLASSIFICAÇÃO DE INTENÇÃO ====================

    def get_classification(self, message_hash: str) -> Optional[Dict[str, Any]]:
        """Busca classificação de intenção cacheada."""
        return self._cache.get("ai_classification", message_hash)

    def set_classification(
        self, 
        message: str, 
        intent: str, 
        confidence: float, 
        entities: Dict = None
    ) -> None:
        """Cacheia classificação de intenção."""
        message_hash = hashlib.md5(message.lower().strip().encode()).hexdigest()
        data = {
            "intent": intent,
            "confidence": confidence,
            "entities": entities or {},
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        self._cache.set("ai_classification", message_hash, data, self.TTL_CLASSIFICATION)
        logger.debug(f"[CACHE] Classificação cacheada: {intent} ({confidence:.2f})")

    def get_classification_by_message(self, message: str) -> Optional[Dict[str, Any]]:
        """Busca classificação pelo texto da mensagem."""
        message_hash = hashlib.md5(message.lower().strip().encode()).hexdigest()
        return self.get_classification(message_hash)

    # ==================== RESUMO FINANCEIRO ====================

    def get_finance_summary(self, user_id: int, year: int, month: int) -> Optional[Dict]:
        """Busca resumo financeiro cacheado."""
        return self._cache.get("ai_finance", f"{user_id}:{year}:{month}")

    def set_finance_summary(
        self, 
        user_id: int, 
        year: int, 
        month: int, 
        summary: Dict
    ) -> None:
        """Cacheia resumo financeiro."""
        self._cache.set("ai_finance", f"{user_id}:{year}:{month}", summary, self.TTL_FINANCE_SUMMARY)

    def invalidate_finance(self, user_id: int) -> None:
        """Invalida cache financeiro (após nova transação)."""
        now = datetime.now(timezone.utc)
        # Invalida mês atual e anterior
        self._cache.delete("ai_finance", f"{user_id}:{now.year}:{now.month}")
        if now.month == 1:
            self._cache.delete("ai_finance", f"{user_id}:{now.year-1}:12")
        else:
            self._cache.delete("ai_finance", f"{user_id}:{now.year}:{now.month-1}")

    # ==================== EMBEDDINGS ====================

    def get_embedding_search(self, user_id: int, query_hash: str) -> Optional[List[Dict]]:
        """Busca resultado de busca semântica cacheado."""
        return self._cache.get("ai_embedding", f"{user_id}:{query_hash}")

    def set_embedding_search(
        self, 
        user_id: int, 
        query: str, 
        results: List[Dict]
    ) -> None:
        """Cacheia resultado de busca semântica."""
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
        self._cache.set("ai_embedding", f"{user_id}:{query_hash}", results, self.TTL_EMBEDDING)

    def get_embedding_search_by_query(self, user_id: int, query: str) -> Optional[List[Dict]]:
        """Busca resultado de busca pelo texto da query."""
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
        return self.get_embedding_search(user_id, query_hash)

    # ==================== DADOS DO USUÁRIO ====================

    def get_user_data_summary(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Busca resumo de dados do usuário cacheado."""
        return self._cache.get("ai_user_data", str(user_id))

    def set_user_data_summary(self, user_id: int, data: Dict[str, Any]) -> None:
        """Cacheia resumo de dados do usuário."""
        self._cache.set("ai_user_data", str(user_id), data, self.TTL_USER_CONTEXT)

    # ==================== COMPORTAMENTO DO USUÁRIO ====================

    def get_behavior(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Busca análise de comportamento cacheada."""
        return self._cache.get("ai_behavior", str(user_id))

    def set_behavior(self, user_id: int, behavior: Dict[str, Any]) -> None:
        """Cacheia análise de comportamento."""
        self._cache.set("ai_behavior", str(user_id), behavior, self.TTL_PREFERENCES)

    # ==================== AÇÕES RECENTES ====================

    def get_recent_actions(self, user_id: int) -> Optional[List[Dict]]:
        """Busca ações recentes cacheadas."""
        return self._cache.get("ai_actions", str(user_id))

    def set_recent_actions(self, user_id: int, actions: List[Dict]) -> None:
        """Cacheia ações recentes."""
        self._cache.set("ai_actions", str(user_id), actions, self.TTL_USER_CONTEXT)

    def add_recent_action(self, user_id: int, action: Dict) -> None:
        """Adiciona ação recente ao cache."""
        actions = self.get_recent_actions(user_id) or []
        actions = actions[-19:] + [action]  # Manter últimas 20
        self.set_recent_actions(user_id, actions)

    # ==================== INVALIDAÇÃO EM MASSA ====================

    def invalidate_user(self, user_id: int) -> None:
        """Invalida todo o cache de um usuário."""
        self.invalidate_full_context(user_id)
        self.invalidate_conversation(user_id)
        self.invalidate_facts(user_id)
        self.invalidate_finance(user_id)
        self._cache.delete("ai_preferences", str(user_id))
        self._cache.delete("ai_user_data", str(user_id))
        self._cache.delete("ai_behavior", str(user_id))
        self._cache.delete("ai_actions", str(user_id))
        logger.info(f"[CACHE] Todo cache invalidado para user {user_id}")

    def invalidate_after_action(self, user_id: int, action: str) -> None:
        """
        Invalida cache apropriado após uma ação.
        
        Args:
            user_id: ID do usuário
            action: Tipo de ação executada
        """
        # Sempre invalida contexto completo após ações
        self.invalidate_full_context(user_id)
        self._cache.delete("ai_user_data", str(user_id))

        # Invalidações específicas por tipo de ação
        if action in ("create_finance", "delete_finance", "update_finance", "query_finance"):
            self.invalidate_finance(user_id)
        
        if action in ("create_reminder", "delete_reminder", "update_reminder", "list_reminders"):
            pass  # Já invalidou contexto
        
        if action in ("create_contact", "delete_contact", "update_contact"):
            pass  # Já invalidou contexto

        logger.debug(f"[CACHE] Cache invalidado após ação: {action}")


# Singleton
_ai_cache: Optional[AIContextCache] = None


def get_ai_cache() -> AIContextCache:
    """Retorna instância singleton do cache de IA."""
    global _ai_cache
    if _ai_cache is None:
        _ai_cache = AIContextCache()
    return _ai_cache

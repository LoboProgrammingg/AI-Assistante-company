"""
Cache especializado para contexto da IA IRIS.

Otimizado para:
- Manter contexto completo do usuário entre requisições
- Histórico de conversa persistente
- Fatos aprendidos sobre o usuário
- Classificações de intenção
- Embeddings e buscas semânticas

A IA NUNCA perde contexto com este sistema.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.cache.manager import CacheManager, CacheNamespace, get_cache

logger = logging.getLogger(__name__)


class AIContextCache:
    """
    Cache especializado para contexto da IA.
    
    Features:
    - Contexto completo do usuário (finanças, lembretes, etc)
    - Histórico de conversa com sliding window
    - Fatos aprendidos persistentes
    - Cache de classificações de intenção
    - Embeddings para busca semântica
    - Invalidação inteligente por tipo de ação
    """
    
    TTL_CONTEXT = 300  # 5 minutos
    TTL_CONVERSATION = 86400  # 24 horas - histórico deve persistir!
    TTL_FACTS = 1800
    TTL_PREFERENCES = 900
    TTL_CLASSIFICATION = 300
    TTL_EMBEDDING = 3600
    TTL_FINANCE = 300
    TTL_SESSION = 14400
    TTL_WORKING_MEMORY = 86400
    
    MAX_CONVERSATION_MESSAGES = 40  # Aumentado para 40 mensagens
    MAX_RECENT_ACTIONS = 20
    
    def __init__(self, cache: Optional[CacheManager] = None):
        self._cache = cache or get_cache()
    
    def _user_key(self, user_id: int, suffix: str = "") -> str:
        """Gera chave baseada no user_id."""
        if suffix:
            return f"{user_id}:{suffix}"
        return str(user_id)
    
    def _hash_text(self, text: str) -> str:
        """Gera hash MD5 de um texto."""
        return hashlib.md5(text.lower().strip().encode()).hexdigest()
    
    def get_full_context(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Busca contexto completo do usuário.
        
        Inclui: finanças, lembretes, contatos, reuniões, metas.
        """
        return self._cache.get(
            CacheNamespace.AI_CONTEXT,
            self._user_key(user_id, "full")
        )
    
    def set_full_context(self, user_id: int, context: Dict[str, Any]) -> None:
        """Cacheia contexto completo do usuário."""
        context["cached_at"] = datetime.now(timezone.utc).isoformat()
        
        self._cache.set(
            CacheNamespace.AI_CONTEXT,
            self._user_key(user_id, "full"),
            context,
            self.TTL_CONTEXT
        )
        logger.debug(f"[AI_CACHE] Contexto completo cacheado para user {user_id}")
    
    def invalidate_context(self, user_id: int) -> None:
        """Invalida contexto completo do usuário."""
        self._cache.delete(CacheNamespace.AI_CONTEXT, self._user_key(user_id, "full"))
        logger.debug(f"[AI_CACHE] Contexto invalidado para user {user_id}")
    
    def get_conversation(self, user_id: int) -> Optional[List[Dict]]:
        """Busca histórico de conversa."""
        return self._cache.get(
            CacheNamespace.AI_CONVERSATION,
            self._user_key(user_id)
        )
    
    def set_conversation(self, user_id: int, messages: List[Dict]) -> None:
        """Cacheia histórico de conversa com sliding window."""
        messages = messages[-self.MAX_CONVERSATION_MESSAGES:]
        
        self._cache.set(
            CacheNamespace.AI_CONVERSATION,
            self._user_key(user_id),
            messages,
            self.TTL_CONVERSATION
        )
    
    def add_message(self, user_id: int, role: str, content: str) -> None:
        """Adiciona mensagem ao histórico."""
        messages = self.get_conversation(user_id) or []
        
        messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        self.set_conversation(user_id, messages)
    
    def invalidate_conversation(self, user_id: int) -> None:
        """Invalida histórico de conversa."""
        self._cache.delete(CacheNamespace.AI_CONVERSATION, self._user_key(user_id))
    
    def get_learned_facts(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Busca fatos aprendidos sobre o usuário."""
        return self._cache.get(
            CacheNamespace.AI_FACTS,
            self._user_key(user_id)
        )
    
    def set_learned_facts(self, user_id: int, facts: Dict[str, Any]) -> None:
        """Cacheia fatos aprendidos."""
        facts["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        self._cache.set(
            CacheNamespace.AI_FACTS,
            self._user_key(user_id),
            facts,
            self.TTL_FACTS
        )
    
    def add_fact(self, user_id: int, category: str, fact: str) -> None:
        """Adiciona um fato aprendido."""
        facts = self.get_learned_facts(user_id) or {"categories": {}}
        
        if category not in facts["categories"]:
            facts["categories"][category] = []
        
        if fact not in facts["categories"][category]:
            facts["categories"][category].append(fact)
        
        self.set_learned_facts(user_id, facts)
    
    def invalidate_facts(self, user_id: int) -> None:
        """Invalida fatos aprendidos."""
        self._cache.delete(CacheNamespace.AI_FACTS, self._user_key(user_id))
    
    def get_preferences(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Busca preferências do usuário."""
        return self._cache.get(
            CacheNamespace.USER_PREFERENCES,
            self._user_key(user_id)
        )
    
    def set_preferences(self, user_id: int, prefs: Dict[str, Any]) -> None:
        """Cacheia preferências do usuário."""
        self._cache.set(
            CacheNamespace.USER_PREFERENCES,
            self._user_key(user_id),
            prefs,
            self.TTL_PREFERENCES
        )
    
    def get_classification(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Busca classificação de intenção cacheada.
        
        Args:
            message: Mensagem original
            
        Returns:
            Dict com intent, confidence, entities ou None
        """
        message_hash = self._hash_text(message)
        return self._cache.get(CacheNamespace.AI_CLASSIFICATION, message_hash)
    
    def set_classification(
        self,
        message: str,
        intent: str,
        confidence: float,
        entities: Optional[Dict] = None,
        action: Optional[str] = None
    ) -> None:
        """
        Cacheia classificação de intenção.
        
        Args:
            message: Mensagem original
            intent: Intenção classificada
            confidence: Confiança (0-1)
            entities: Entidades extraídas
            action: Ação decidida
        """
        message_hash = self._hash_text(message)
        
        data = {
            "intent": intent,
            "confidence": confidence,
            "entities": entities or {},
            "action": action,
            "cached_at": datetime.now(timezone.utc).isoformat()
        }
        
        self._cache.set(
            CacheNamespace.AI_CLASSIFICATION,
            message_hash,
            data,
            self.TTL_CLASSIFICATION
        )
        logger.debug(f"[AI_CACHE] Classificação cacheada: {intent} ({confidence:.0%})")
    
    def get_finance_summary(
        self,
        user_id: int,
        year: int,
        month: int
    ) -> Optional[Dict]:
        """Busca resumo financeiro cacheado."""
        key = f"{user_id}:{year}:{month}"
        return self._cache.get(CacheNamespace.FINANCE, key)
    
    def set_finance_summary(
        self,
        user_id: int,
        year: int,
        month: int,
        summary: Dict
    ) -> None:
        """Cacheia resumo financeiro."""
        key = f"{user_id}:{year}:{month}"
        summary["cached_at"] = datetime.now(timezone.utc).isoformat()
        
        self._cache.set(CacheNamespace.FINANCE, key, summary, self.TTL_FINANCE)
    
    def invalidate_finance(self, user_id: int) -> None:
        """Invalida cache financeiro do usuário."""
        now = datetime.now(timezone.utc)
        
        self._cache.delete(CacheNamespace.FINANCE, f"{user_id}:{now.year}:{now.month}")
        
        if now.month == 1:
            self._cache.delete(CacheNamespace.FINANCE, f"{user_id}:{now.year-1}:12")
        else:
            self._cache.delete(CacheNamespace.FINANCE, f"{user_id}:{now.year}:{now.month-1}")
    
    def get_embedding_search(self, user_id: int, query: str) -> Optional[List[Dict]]:
        """Busca resultado de busca semântica cacheado."""
        query_hash = self._hash_text(query)
        return self._cache.get(
            CacheNamespace.AI_EMBEDDING,
            f"{user_id}:{query_hash}"
        )
    
    def set_embedding_search(
        self,
        user_id: int,
        query: str,
        results: List[Dict]
    ) -> None:
        """Cacheia resultado de busca semântica."""
        query_hash = self._hash_text(query)
        
        self._cache.set(
            CacheNamespace.AI_EMBEDDING,
            f"{user_id}:{query_hash}",
            results,
            self.TTL_EMBEDDING
        )
    
    def get_session_context(
        self,
        user_id: int,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Busca contexto de sessão."""
        return self._cache.get(
            CacheNamespace.USER_SESSION,
            f"{user_id}:{session_id}"
        )
    
    def set_session_context(
        self,
        user_id: int,
        session_id: str,
        context: Dict[str, Any]
    ) -> None:
        """Cacheia contexto de sessão."""
        context["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        self._cache.set(
            CacheNamespace.USER_SESSION,
            f"{user_id}:{session_id}",
            context,
            self.TTL_SESSION
        )
    
    def update_session_context(
        self,
        user_id: int,
        session_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """Atualiza contexto de sessão (merge)."""
        current = self.get_session_context(user_id, session_id) or {}
        current.update(updates)
        self.set_session_context(user_id, session_id, current)
    
    def get_behavior(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Busca análise de comportamento do usuário."""
        return self._cache.get(
            CacheNamespace.AI_BEHAVIOR,
            self._user_key(user_id)
        )
    
    def set_behavior(self, user_id: int, behavior: Dict[str, Any]) -> None:
        """Cacheia análise de comportamento."""
        self._cache.set(
            CacheNamespace.AI_BEHAVIOR,
            self._user_key(user_id),
            behavior,
            self.TTL_PREFERENCES
        )
    
    def get_recent_actions(self, user_id: int) -> Optional[List[Dict]]:
        """Busca ações recentes do usuário."""
        return self._cache.get(
            CacheNamespace.AI_CONTEXT,
            self._user_key(user_id, "actions")
        )
    
    def add_recent_action(self, user_id: int, action: Dict) -> None:
        """Adiciona ação recente."""
        actions = self.get_recent_actions(user_id) or []
        
        action["timestamp"] = datetime.now(timezone.utc).isoformat()
        actions = actions[-(self.MAX_RECENT_ACTIONS - 1):] + [action]
        
        self._cache.set(
            CacheNamespace.AI_CONTEXT,
            self._user_key(user_id, "actions"),
            actions,
            self.TTL_CONTEXT
        )
    
    def get_working_memory(self, user_id: int) -> Dict[str, Any]:
        """
        Busca working memory completa do usuário.
        
        Working memory persiste por 24h e contém:
        - Tópicos discutidos
        - Entidades mencionadas
        - Preferências temporárias
        - Estado de fluxos em andamento
        """
        return self._cache.get(
            CacheNamespace.AI_CONTEXT,
            self._user_key(user_id, "working")
        ) or {}
    
    def set_working_memory(self, user_id: int, memory: Dict[str, Any]) -> None:
        """Salva working memory."""
        memory["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        self._cache.set(
            CacheNamespace.AI_CONTEXT,
            self._user_key(user_id, "working"),
            memory,
            self.TTL_WORKING_MEMORY
        )
    
    def update_working_memory(self, user_id: int, key: str, value: Any) -> None:
        """Atualiza item específico da working memory."""
        memory = self.get_working_memory(user_id)
        memory[key] = value
        self.set_working_memory(user_id, memory)
    
    def invalidate_user(self, user_id: int) -> None:
        """Invalida todo o cache de um usuário."""
        self.invalidate_context(user_id)
        self.invalidate_conversation(user_id)
        self.invalidate_facts(user_id)
        self.invalidate_finance(user_id)
        
        self._cache.delete(CacheNamespace.USER_PREFERENCES, self._user_key(user_id))
        self._cache.delete(CacheNamespace.AI_BEHAVIOR, self._user_key(user_id))
        self._cache.delete(CacheNamespace.AI_CONTEXT, self._user_key(user_id, "actions"))
        self._cache.delete(CacheNamespace.AI_CONTEXT, self._user_key(user_id, "working"))
        
        logger.info(f"[AI_CACHE] Todo cache invalidado para user {user_id}")
    
    def invalidate_after_action(self, user_id: int, action: str) -> None:
        """
        Invalida cache apropriado após uma ação.
        
        Estratégia inteligente: invalida apenas o necessário.
        """
        self.invalidate_context(user_id)
        
        finance_actions = {
            "create_finance", "delete_finance", "update_finance",
            "query_finance", "create_goal", "update_goal"
        }
        if action in finance_actions:
            self.invalidate_finance(user_id)
        
        memory_actions = {"create_reminder", "delete_reminder", "create_contact"}
        if action in memory_actions:
            self.invalidate_facts(user_id)
        
        logger.debug(f"[AI_CACHE] Cache invalidado após ação: {action}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache de IA."""
        return {
            "type": "ai_context_cache",
            "ttls": {
                "context": self.TTL_CONTEXT,
                "conversation": self.TTL_CONVERSATION,
                "facts": self.TTL_FACTS,
                "classification": self.TTL_CLASSIFICATION,
                "working_memory": self.TTL_WORKING_MEMORY,
            },
            "limits": {
                "max_conversation_messages": self.MAX_CONVERSATION_MESSAGES,
                "max_recent_actions": self.MAX_RECENT_ACTIONS,
            },
            "backend": self._cache.get_stats()
        }


_ai_cache: Optional[AIContextCache] = None


def get_ai_cache() -> AIContextCache:
    """Retorna instância singleton do AIContextCache."""
    global _ai_cache
    if _ai_cache is None:
        _ai_cache = AIContextCache()
    return _ai_cache

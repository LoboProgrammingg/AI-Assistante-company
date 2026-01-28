"""
MemoryManager - Gerenciador de memória do usuário.

Integrado com AIContextCache para persistência real entre requests.
Usa PostgreSQL (MemoryService) como fonte primária e Redis como cache.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.cache import get_ai_cache, AIContextCache
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Gerenciador de memória do usuário.
    
    Arquitetura de cache em camadas:
    1. Cache local (instância) - mais rápido, vida curta
    2. Redis (AIContextCache) - persistente entre requests
    3. PostgreSQL (MemoryService) - fonte de verdade
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.service = MemoryService(db)
        self._ai_cache: AIContextCache = get_ai_cache()
        self._local_cache: Dict[str, Any] = {}

    def get_full_context(self) -> Dict[str, Any]:
        """
        Retorna contexto completo do usuário.
        
        Estratégia:
        1. Verifica cache local (instância)
        2. Verifica Redis (AIContextCache)
        3. Busca do PostgreSQL e popula caches
        """
        if "full_context" in self._local_cache:
            return self._local_cache["full_context"]
        
        cached = self._ai_cache.get_learned_facts(self.user_id)
        if cached and "preferences" in cached and "facts" in cached:
            self._local_cache["full_context"] = cached
            return cached

        context = {
            "preferences": self._load_preferences(),
            "facts": self._load_facts(),
            "conversation_context": self._load_conversation_context(),
        }

        self._local_cache["full_context"] = context
        self._ai_cache.set_learned_facts(self.user_id, context)
        
        return context

    def _load_preferences(self) -> List[str]:
        """Carrega preferências do PostgreSQL."""
        data = self.service.get_memory(self.user_id, "preferences")
        if data and isinstance(data, dict):
            return data.get("items", [])
        return []

    def _load_facts(self) -> List[Dict[str, Any]]:
        """Carrega fatos do PostgreSQL."""
        data = self.service.get_memory(self.user_id, "facts")
        if data and isinstance(data, dict):
            return data.get("items", [])
        return []

    def _load_conversation_context(self) -> Dict[str, Any]:
        """Carrega contexto de conversação do PostgreSQL."""
        data = self.service.get_memory(self.user_id, "conversation_context")
        return data if data else {}

    def get_preferences(self) -> List[str]:
        """Retorna preferências do usuário."""
        context = self.get_full_context()
        return context.get("preferences", [])

    def get_facts(self) -> List[Dict[str, Any]]:
        """Retorna fatos conhecidos sobre o usuário."""
        context = self.get_full_context()
        return context.get("facts", [])

    def get_conversation_context(self) -> Dict[str, Any]:
        """Retorna contexto de conversação."""
        context = self.get_full_context()
        return context.get("conversation_context", {})

    def add_preference(self, preference: str) -> None:
        """Adiciona uma preferência do usuário."""
        data = self.service.get_memory(self.user_id, "preferences") or {"items": []}
        items = data.get("items", [])

        if preference not in items:
            items.append(preference)
            self.service.set_memory(self.user_id, "preferences", {"items": items})
            self._invalidate_caches()

    def add_fact(self, fact: str, category: str = "general") -> None:
        """Adiciona um fato sobre o usuário."""
        data = self.service.get_memory(self.user_id, "facts") or {"items": []}
        items = data.get("items", [])

        fact_entry = {"content": fact, "category": category}

        existing = [f for f in items if f.get("content") == fact]
        if not existing:
            items.append(fact_entry)
            self.service.set_memory(self.user_id, "facts", {"items": items})
            self._invalidate_caches()
            
            self._ai_cache.add_fact(self.user_id, category, fact)

    def build_context_prompt(self, user_name: str = None) -> str:
        """Constrói prompt de contexto para o LLM."""
        context = self.get_full_context()

        parts = []

        if user_name:
            parts.append(f"Usuário: {user_name}")

        preferences = context.get("preferences", [])
        if preferences:
            parts.append(f"Preferências: {', '.join(preferences[:5])}")

        facts = context.get("facts", [])
        if facts:
            fact_texts = [f.get("content", "") for f in facts[:5]]
            parts.append(f"Fatos conhecidos: {'; '.join(fact_texts)}")

        return " | ".join(parts) if parts else "Novo usuário"

    def _invalidate_caches(self) -> None:
        """Invalida todos os caches do usuário."""
        self._local_cache.clear()
        self._ai_cache.invalidate_facts(self.user_id)

    def clear_cache(self) -> None:
        """Limpa cache interno e Redis."""
        self._invalidate_caches()

    def learn_from_message(
        self,
        message: str,
        intent: str = "",
        entities: Dict[str, Any] = None,
        response: str = "",
    ) -> None:
        """
        Aprende com a mensagem processada.

        Extrai informações relevantes e armazena para contexto futuro.
        """
        if not message:
            return

        try:
            conv_context = self._load_conversation_context()
            conv_context["last_intent"] = intent
            conv_context["last_entities"] = entities or {}
            conv_context["last_message"] = message[:200]

            self.service.set_memory(self.user_id, "conversation_context", conv_context)
            self._invalidate_caches()
            
            self._ai_cache.add_message(self.user_id, "user", message)
            if response:
                self._ai_cache.add_message(self.user_id, "assistant", response)
                
        except Exception as e:
            logger.warning(f"Erro ao aprender da mensagem: {e}")

    def get_recent_messages(self, limit: int = 10) -> List[Dict]:
        """Retorna últimas mensagens do histórico."""
        messages = self._ai_cache.get_conversation(self.user_id)
        if messages:
            return messages[-limit:]
        return []

    def get_working_memory(self) -> Dict[str, Any]:
        """Retorna working memory da IA para este usuário."""
        return self._ai_cache.get_working_memory(self.user_id)

    def update_working_memory(self, key: str, value: Any) -> None:
        """Atualiza item na working memory."""
        self._ai_cache.update_working_memory(self.user_id, key, value)

"""
MemoryManager - Gerenciador de memória do usuário.

Wrapper simplificado sobre o MemoryService para compatibilidade.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class MemoryManager:
    """Gerenciador de memória do usuário."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.service = MemoryService(db)
        self._cache: Dict[str, Any] = {}

    def get_full_context(self) -> Dict[str, Any]:
        """Retorna contexto completo do usuário."""
        if "full_context" in self._cache:
            return self._cache["full_context"]

        context = {
            "preferences": self.get_preferences(),
            "facts": self.get_facts(),
            "conversation_context": self.get_conversation_context(),
        }

        self._cache["full_context"] = context
        return context

    def get_preferences(self) -> List[str]:
        """Retorna preferências do usuário."""
        data = self.service.get_memory(self.user_id, "preferences")
        if data and isinstance(data, dict):
            return data.get("items", [])
        return []

    def get_facts(self) -> List[Dict[str, Any]]:
        """Retorna fatos conhecidos sobre o usuário."""
        data = self.service.get_memory(self.user_id, "facts")
        if data and isinstance(data, dict):
            return data.get("items", [])
        return []

    def get_conversation_context(self) -> Dict[str, Any]:
        """Retorna contexto de conversação."""
        data = self.service.get_memory(self.user_id, "conversation_context")
        return data if data else {}

    def add_preference(self, preference: str) -> None:
        """Adiciona uma preferência do usuário."""
        data = self.service.get_memory(self.user_id, "preferences") or {"items": []}
        items = data.get("items", [])

        if preference not in items:
            items.append(preference)
            self.service.set_memory(self.user_id, "preferences", {"items": items})
            self._cache.pop("full_context", None)

    def add_fact(self, fact: str, category: str = "general") -> None:
        """Adiciona um fato sobre o usuário."""
        data = self.service.get_memory(self.user_id, "facts") or {"items": []}
        items = data.get("items", [])

        fact_entry = {"content": fact, "category": category}

        # Evitar duplicatas
        existing = [f for f in items if f.get("content") == fact]
        if not existing:
            items.append(fact_entry)
            self.service.set_memory(self.user_id, "facts", {"items": items})
            self._cache.pop("full_context", None)

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

    def clear_cache(self) -> None:
        """Limpa cache interno."""
        self._cache.clear()

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

        # Atualizar contexto de conversação
        try:
            conv_context = self.get_conversation_context()
            conv_context["last_intent"] = intent
            conv_context["last_entities"] = entities or {}

            self.service.set_memory(self.user_id, "conversation_context", conv_context)
            self._cache.pop("full_context", None)
        except Exception as e:
            logger.warning(f"Erro ao aprender da mensagem: {e}")

"""
Agent Registry - Registro centralizado de agentes especializados.

Mapeia intents para agentes e gerencia instâncias.
"""

import logging
from typing import TYPE_CHECKING, Dict, Optional, Type

from app.ai.agents.base import SpecializedAgent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registro centralizado de agentes especializados."""

    _agents: Dict[str, Type[SpecializedAgent]] = {}
    _intent_mapping: Dict[str, str] = {}

    @classmethod
    def register(cls, agent_class: Type[SpecializedAgent]) -> Type[SpecializedAgent]:
        """
        Decorator para registrar um agente.

        Uso:
            @AgentRegistry.register
            class BillsAgent(SpecializedAgent):
                name = "bills"
                supported_intents = ["bills", "invoice", "fatura"]
        """
        name = agent_class.name
        cls._agents[name] = agent_class

        # Mapear intents para este agente
        for intent in agent_class.supported_intents:
            cls._intent_mapping[intent] = name

        logger.info(f"[REGISTRY] Registrado: {name} ({len(agent_class.supported_intents)} intents)")
        return agent_class

    @classmethod
    def get_agent(cls, name: str, db: "Session" = None, user_id: int = None) -> Optional[SpecializedAgent]:
        """Retorna instância de um agente pelo nome."""
        agent_class = cls._agents.get(name)
        if agent_class:
            return agent_class(db=db, user_id=user_id)
        return None

    @classmethod
    def get_agent_for_intent(cls, intent: str, db: "Session" = None, user_id: int = None) -> Optional[SpecializedAgent]:
        """Retorna agente apropriado para um intent."""
        agent_name = cls._intent_mapping.get(intent)
        if agent_name:
            return cls.get_agent(agent_name, db=db, user_id=user_id)
        return None

    @classmethod
    def list_agents(cls) -> Dict[str, list]:
        """Lista todos os agentes registrados e seus intents."""
        return {name: agent.supported_intents for name, agent in cls._agents.items()}

    @classmethod
    def get_all_intents(cls) -> list:
        """Retorna todos os intents suportados."""
        return list(cls._intent_mapping.keys())


def get_agent_for_intent(intent: str, db: "Session" = None, user_id: int = None) -> Optional[SpecializedAgent]:
    """Atalho para obter agente por intent."""
    return AgentRegistry.get_agent_for_intent(intent, db=db, user_id=user_id)

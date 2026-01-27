"""
Agent Dispatcher - Integração dos agentes especializados com o Graph v3.

Responsabilidades:
- Rotear para o agente correto baseado no intent
- Gerenciar ciclo de vida dos agentes
- Aplicar confidence scoring antes de executar
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from app.ai.agents.base import AgentResult
from app.ai.agents.confidence import calculate_action_confidence
from app.ai.agents.registry import AgentRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Mapeamento de intents para agentes especializados
SPECIALIZED_INTENTS = {
    # Bills Agent
    "bills": "bills",
    "invoice": "bills",
    "fatura": "bills",
    "boleto": "bills",
    # Memory Agent
    "memory": "memory",
    "preference": "memory",
    "remember": "memory",
    # Patterns Agent
    "patterns": "patterns",
    "anomaly": "patterns",
    "insight": "patterns",
    "analise": "patterns",
    "padrão": "patterns",
    # Goals Agent
    "goals": "goals",
    "meta": "goals",
    "objetivo": "goals",
    "economizar": "goals",
    "poupar": "goals",
    # Subscriptions Agent
    "subscriptions": "subscriptions",
    "assinatura": "subscriptions",
    "recorrente": "subscriptions",
    # Advisor Agent
    "advisor": "advisor",
    "conselho": "advisor",
    "simular": "advisor",
    "projeção": "advisor",
    # Health Agent
    "health": "health",
    "saúde": "health",
    "remédio": "health",
    "consulta": "health",
}


async def dispatch_to_agent(
    intent: str,
    message: str,
    entities: Dict[str, Any],
    db: "Session" = None,
    user_id: int = None,
) -> Optional[AgentResult]:
    """
    Despacha mensagem para agente especializado.

    Args:
        intent: Intenção classificada
        message: Mensagem original
        entities: Entidades extraídas
        db: Sessão do banco
        user_id: ID do usuário

    Returns:
        AgentResult se agente encontrado, None se não
    """
    agent_name = SPECIALIZED_INTENTS.get(intent)

    if not agent_name:
        return None

    agent = AgentRegistry.get_agent(agent_name, db=db, user_id=user_id)

    if not agent:
        logger.warning(f"[DISPATCHER] Agente '{agent_name}' não encontrado")
        return None

    logger.info(f"[DISPATCHER] Roteando para {agent_name.upper()} Agent")

    try:
        result = await agent.process(message, entities)

        # Aplicar confidence scoring se houver ação
        if result.action and result.data:
            confidence = calculate_action_confidence(result.action, result.data)

            # Sobrescrever flags baseado no scoring global
            if confidence.only_suggest:
                result.requires_confirmation = True
            elif confidence.requires_confirmation:
                result.requires_confirmation = True

            result.confidence = confidence.score

            logger.info(
                f"[DISPATCHER] {agent_name}: {result.action} | "
                f"Confidence: {confidence.score:.0%} | "
                f"Confirm: {result.requires_confirmation}"
            )

        return result

    except Exception as e:
        logger.error(f"[DISPATCHER] Erro no agente {agent_name}: {e}")
        return AgentResult(
            success=False,
            action="error",
            error=str(e),
            message=f"Erro ao processar com {agent_name}: {str(e)}",
        )


def is_specialized_intent(intent: str) -> bool:
    """Verifica se intent tem agente especializado."""
    return intent in SPECIALIZED_INTENTS


def get_available_agents() -> Dict[str, list]:
    """Lista agentes disponíveis e seus intents."""
    return {
        "specialized_intents": list(SPECIALIZED_INTENTS.keys()),
        "registered_agents": AgentRegistry.list_agents(),
    }

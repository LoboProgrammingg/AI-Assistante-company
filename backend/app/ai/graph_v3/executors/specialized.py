"""
Specialized Executor - Integração dos agentes especializados.

Despacha ações para BillsAgent, MemoryAgent, etc.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

# Importar agentes para garantir que sejam registrados
import app.ai.agents  # noqa: F401

logger = logging.getLogger(__name__)


# Intents que usam agentes especializados
SPECIALIZED_INTENTS = {"bills", "memory", "patterns", "goals", "advisor", "health", "subscriptions"}

# Ações que usam agentes especializados
SPECIALIZED_ACTIONS = {
    # Bills
    "extract_invoice",
    "list_bills", 
    "create_bill_reminder",
    # Memory
    "save_preference",
    "read_memory",
    "delete_memory",
    # Patterns
    "analyze_patterns",
    "detect_anomalies",
    # Goals
    "create_goal",
    "list_goals",
    "goal_progress",
    # Subscriptions
    "list_subscriptions",
    "analyze_subscriptions",
    # Advisor
    "simulate_scenario",
    "run_projection",
    "financial_state",
    # Health
    "create_health_reminder",
    "health_schedule",
}


class SpecializedExecutor:
    """Executor para agentes especializados."""
    
    @staticmethod
    async def execute(action_type: str, params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Executa ação via agente especializado."""
        from app.ai.agents.dispatcher import dispatch_to_agent
        
        # Mapear ação para intent
        action_to_intent = {
            # Bills
            "extract_invoice": "bills",
            "list_bills": "bills",
            "create_bill_reminder": "bills",
            # Memory
            "save_preference": "memory",
            "read_memory": "memory",
            "delete_memory": "memory",
            # Patterns
            "analyze_patterns": "patterns",
            "detect_anomalies": "patterns",
            # Goals
            "create_goal": "goals",
            "list_goals": "goals",
            "goal_progress": "goals",
            # Subscriptions
            "list_subscriptions": "subscriptions",
            "analyze_subscriptions": "subscriptions",
            # Advisor
            "simulate_scenario": "advisor",
            "run_projection": "advisor",
            "financial_state": "advisor",
            # Health
            "create_health_reminder": "health",
            "health_schedule": "health",
        }
        
        intent = action_to_intent.get(action_type)
        
        logger.info(f"[SPECIALIZED] Action: {action_type} -> Intent: {intent}")
        logger.info(f"[SPECIALIZED] Params: {list(params.keys())}")
        
        if not intent:
            return ExecutionResult(
                success=False,
                action_type=action_type,
                error=f"Ação '{action_type}' não mapeada para agente",
            )
        
        try:
            # Construir mensagem para o agente
            message = params.get("original_message", "")
            if not message and params.get("ocr_text"):
                message = params["ocr_text"]
            
            logger.info(f"[SPECIALIZED] Message: {message[:100]}..." if len(message) > 100 else f"[SPECIALIZED] Message: {message}")
            
            # Despachar para agente
            result = await dispatch_to_agent(
                intent=intent,
                message=message,
                entities=params,
                db=db,
                user_id=user_id,
            )
            
            if result is None:
                return ExecutionResult(
                    success=False,
                    action_type=action_type,
                    error=f"Agente '{intent}' não encontrado",
                )
            
            logger.info(f"[SPECIALIZED] Result: success={result.success}, action={result.action}")
            logger.info(f"[SPECIALIZED] Response: {result.message[:200] if result.message else 'None'}...")
            
            return ExecutionResult(
                success=result.success,
                action_type=action_type,
                data=result.data,
                error=result.error,
                response_template=result.message if result.success else None,
            )
            
        except Exception as e:
            logger.error(f"[SPECIALIZED] Erro: {e}")
            return ExecutionResult(
                success=False,
                action_type=action_type,
                error=str(e),
            )
    
    @staticmethod
    def is_specialized_action(action_type: str) -> bool:
        """Verifica se ação usa agente especializado."""
        return action_type in SPECIALIZED_ACTIONS


def is_specialized_action(action_type: str) -> bool:
    """Atalho para verificar ação especializada."""
    return SpecializedExecutor.is_specialized_action(action_type)

"""
Tipos e definições de estado do IRIS v3.

Mudanças:
- Campos mais específicos para reduzir ambiguidade
- Estrutura de ação padronizada
- Suporte a early exit (respostas template)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import MessagesState
from pydantic import ConfigDict

# Tipos de ação que o sistema suporta
ActionType = Literal[
    # Finanças
    "create_finance",
    "query_finance",
    "delete_finance",
    "update_finance",
    # Lembretes
    "create_reminder",
    "list_reminders",
    "delete_reminder",
    "update_reminder",
    # Reuniões (transcrição de áudio)
    "create_meeting",
    "list_meetings",
    # Calendar (Google)
    "create_event",
    "list_events",
    "check_availability",
    # Tarefas
    "create_task",
    "list_tasks",
    "complete_task",
    "delete_task",
    "task_summary",
    # Mensagens
    "schedule_message",
    "list_scheduled_messages",
    # Integrações
    "web_search",
    "search_news",
    "get_weather",
    # Especiais
    "summarize_transcription",
    # Respostas
    "direct_response",
    "needs_llm_response",
    # Nenhuma ação
    "none",
]

# Intenções suportadas
IntentType = Literal[
    "finance", "reminder", "meeting", "calendar", "task", "message", "search", "general", "transcription"
]


@dataclass
class ExtractedAction:
    """Ação extraída pelo cognitive node."""

    action_type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    requires_confirmation: bool = False


@dataclass
class ExecutionResult:
    """Resultado da execução de uma ação."""

    success: bool
    action_type: ActionType
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    response_template: Optional[str] = None


class IRISStateV3(MessagesState):
    """
    Estado otimizado do IRIS v3.

    Fluxo:
    1. cognitive_node preenche: intent, action, entities
    2. executor_node preenche: execution_result
    3. responder_node usa execution_result para gerar resposta
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # === Identificação ===
    user_id: int = 0
    session_id: str = ""
    user_name: str = ""

    # === Database ===
    db: Optional[Any] = None

    # === Classificação ===
    intent: IntentType = "general"
    confidence: float = 0.0

    # === Ação Extraída ===
    action: Optional[ExtractedAction] = None
    entities: Dict[str, Any] = {}

    # === Resultado da Execução ===
    execution_result: Optional[ExecutionResult] = None

    # === Controle de Fluxo ===
    early_exit: bool = False
    response_template: Optional[str] = None

    # === Contexto ===
    context_prompt: str = ""
    rag_context: str = ""

    # === Erro ===
    error: Optional[str] = None


def create_initial_state_v3(
    user_id: int,
    session_id: str,
    message: str,
    user_name: str = "",
    context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Cria estado inicial para o grafo v3."""
    ctx = context or {}

    return {
        "messages": [HumanMessage(content=message)],
        "user_id": user_id,
        "session_id": session_id,
        "user_name": user_name,
        "db": ctx.get("db"),
        "context_prompt": ctx.get("context_prompt", ""),
        "rag_context": ctx.get("rag_context", ""),
        "intent": "general",
        "confidence": 0.0,
        "action": None,
        "entities": {},
        "execution_result": None,
        "early_exit": False,
        "response_template": None,
        "error": None,
    }

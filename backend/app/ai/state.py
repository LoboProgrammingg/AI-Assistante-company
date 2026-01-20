"""
Estado tipado para LangGraph - IRIS.
Seguindo melhores práticas: herda de MessagesState, tipagem rigorosa.
"""

from typing import Any, Dict, List, Literal, Optional

from langgraph.graph import MessagesState
from pydantic import BaseModel


class FinanceContext(BaseModel):
    """Contexto financeiro do usuário."""

    total_expense_month: float = 0.0
    total_income_month: float = 0.0
    balance: float = 0.0
    top_categories: List[str] = []
    recent_transactions: List[Dict[str, Any]] = []


class UserContext(BaseModel):
    """Contexto do usuário."""

    user_id: int
    user_name: str = ""
    timezone: str = "America/Sao_Paulo"
    phone_number: str = ""
    is_audio: bool = False
    communication_style: Dict[str, Any] = {}


class MemoryContext(BaseModel):
    """Contexto de memória."""

    conversation: List[Dict[str, Any]] = []
    facts: Dict[str, Any] = {}
    preferences: Dict[str, Any] = {}
    recent_actions: List[Dict[str, Any]] = []


class PendingAction(BaseModel):
    """Ação pendente de confirmação (HITL)."""

    action_type: str
    entities: Dict[str, Any] = {}
    requires_confirmation: bool = True
    confirmed: bool = False


class IRISState(MessagesState):
    """
    Estado principal do agente IRIS.

    Herda de MessagesState que já fornece:
    - messages: List[BaseMessage] com reducer add_messages

    Adiciona campos específicos do IRIS com tipagem forte.
    """

    # Identificação
    user_id: int = 0
    session_id: str = ""

    # Classificação
    intent: Literal["reminder", "finance", "meeting", "contact", "general", ""] = ""
    confidence: float = 0.0

    # Entidades extraídas (tipado por domínio)
    entities: Dict[str, Any] = {}

    # Ação a ser executada
    next_action: str = ""
    pending_action: Optional[PendingAction] = None

    # Contextos tipados
    user_context: Optional[UserContext] = None
    memory_context: Optional[MemoryContext] = None
    finance_context: Optional[FinanceContext] = None

    # RAG context
    rag_context: str = ""
    context_prompt: str = ""

    # Controle de fluxo
    step_count: int = 0
    max_steps: int = 15
    error: Optional[str] = None

    # Tool calls pendentes
    tool_calls: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []


def create_initial_state(user_id: int, session_id: str, message: str, context: Dict[str, Any] = None) -> IRISState:
    """
    Cria estado inicial para processamento.

    Args:
        user_id: ID do usuário
        session_id: ID da sessão
        message: Mensagem do usuário
        context: Contexto adicional

    Returns:
        Estado inicial configurado
    """
    from langchain_core.messages import HumanMessage

    context = context or {}

    user_ctx = UserContext(
        user_id=user_id,
        user_name=context.get("user_name", ""),
        timezone=context.get("timezone", "America/Sao_Paulo"),
        phone_number=context.get("phone_number", ""),
        is_audio=context.get("is_audio", False),
        communication_style=context.get("communication_style", {}),
    )

    memory_ctx = None
    if context.get("memory"):
        mem = context["memory"]
        memory_ctx = MemoryContext(
            conversation=mem.get("conversation", []),
            facts=mem.get("facts", {}),
            preferences=mem.get("preferences", {}),
            recent_actions=mem.get("recent_actions", []),
        )

    return IRISState(
        messages=[HumanMessage(content=message)],
        user_id=user_id,
        session_id=session_id,
        user_context=user_ctx,
        memory_context=memory_ctx,
        context_prompt=context.get("context_prompt", ""),
        rag_context=context.get("rag_context", ""),
    )

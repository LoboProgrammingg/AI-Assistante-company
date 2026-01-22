"""
Agent Nodes - Agentes especializados por domínio.

Responsável por:
- Processar mensagens usando LLM com tools
- Agentes: finance, reminder, meeting, contact
"""

import logging
from typing import TYPE_CHECKING, List

from langchain_core.messages import SystemMessage

from app.ai.datetime_utils import get_datetime_context
from app.ai.state import IRISState
from app.ai.system_prompts import DomainPrompts

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class AgentNodes:
    """Nós dos agentes especializados."""

    def __init__(self, llm_with_tools: "ChatGoogleGenerativeAI"):
        """
        Args:
            llm_with_tools: LLM com tools vinculadas
        """
        self.llm_with_tools = llm_with_tools

    def finance_agent(self, state: IRISState) -> IRISState:
        """Agente de finanças usando tools."""
        return self._process_with_tools(state, "finance")

    def reminder_agent(self, state: IRISState) -> IRISState:
        """Agente de lembretes usando tools."""
        return self._process_with_tools(state, "reminder")

    def meeting_agent(self, state: IRISState) -> IRISState:
        """Agente de reuniões usando tools."""
        return self._process_with_tools(state, "meeting")

    def contact_agent(self, state: IRISState) -> IRISState:
        """Agente de contatos usando tools."""
        return self._process_with_tools(state, "contact")

    def _process_with_tools(self, state: IRISState, domain: str) -> IRISState:
        """
        Processa mensagem usando LLM com tools.
        O LLM decide qual tool chamar, ToolNode executa.
        """
        last_message = state["messages"][-1]

        # Buscar contexto RAG se disponível
        rag_context = self._get_rag_context(state, last_message.content)

        # Contexto de data/hora atual
        datetime_context = get_datetime_context()

        # Construir prompt completo
        full_system_prompt = DomainPrompts.build_full_prompt(
            domain=domain,
            datetime_context=datetime_context,
            context_prompt=state.get("context_prompt", ""),
            rag_context=rag_context,
        )

        messages = [SystemMessage(content=full_system_prompt), last_message]

        # Chamar LLM com tools
        response = self.llm_with_tools.invoke(messages)

        # Verificar se há tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            state["tool_calls"] = response.tool_calls
            logger.info(f"[AGENT] 🛠️ Tools chamadas: {[tc['name'] for tc in response.tool_calls]}")
        else:
            # ⚠️ PROBLEMA: LLM respondeu sem chamar tools!
            logger.warning(f"[AGENT] ⚠️ LLM respondeu SEM chamar tools para intent={domain}!")
            logger.warning(f"[AGENT] Resposta: {response.content[:200] if response.content else 'vazio'}")
            state["messages"] = list(state["messages"]) + [response]

        return state

    def _get_rag_context(self, state: IRISState, message_content: str) -> str:
        """Busca contexto RAG nos documentos do usuário."""
        db = state.get("db")
        user_id = state.get("user_id")
        
        if not db or not user_id:
            return ""

        try:
            from app.services.embedding_service import EmbeddingService
            embedding_service = EmbeddingService(db)
            rag_context = embedding_service.get_relevant_context(user_id, message_content, max_tokens=1500)
            if rag_context:
                logger.debug(f"[RAG] Contexto encontrado ({len(rag_context)} chars)")
            return rag_context or ""
        except Exception as e:
            logger.debug(f"[RAG] Sem contexto: {e}")
            return ""

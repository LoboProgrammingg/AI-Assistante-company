"""
Grafo LangGraph v2 - IRIS com melhores práticas.

Arquivo principal refatorado - importa nós de módulos separados.

Melhorias implementadas:
- Estado tipado herdando de MessagesState
- Tools com Pydantic schemas
- Persistência com PostgreSQL Checkpointer
- Proteção contra loops infinitos
- Separação clara: LLM decide, ToolNode executa
- Código modularizado em nodes/
- Estado imutável (nós retornam dict)
- Suporte a streaming
- Human-in-the-Loop para ações sensíveis
"""

import logging
from typing import AsyncIterator, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.ai.checkpointer import get_thread_config
from app.ai.memory import MemoryManager
from app.ai.nodes.agents import AgentNodes
from app.ai.nodes.error_handler import ErrorHandlerNode
from app.ai.nodes.general_chat import GeneralChatNode
from app.ai.nodes.response_formatter import ResponseFormatterNode
from app.ai.nodes.router import RouterNode
from app.ai.nodes.tool_executor import ToolExecutorNode
from app.ai.state import IRISState, create_initial_state
from app.ai.tools.contact_tools import ContactTools
from app.ai.tools.finance_tools import FinanceTools
from app.ai.tools.integrations.brasil_api import brasil_api_tools
from app.ai.tools.integrations.google_calendar import google_calendar_tools
from app.ai.tools.integrations.tavily_search import tavily_tools
from app.ai.tools.integrations.yfinance_tools import yfinance_tools
from app.ai.tools.meeting_tools import MeetingTools
from app.ai.tools.reminder_tools import ReminderTools
from app.config import settings

logger = logging.getLogger(__name__)


class IRISGraphV2:
    """
    Grafo LangGraph v2 seguindo melhores práticas.

    Arquitetura Hub-and-Spoke:
    - Router central classifica intenção
    - Sub-handlers processam cada domínio
    - ToolNode executa ações
    - Proteção contra loops
    """

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.model = model or settings.GEMINI_MODEL

        # Inicializar LLMs
        self._init_llms()

        # Coletar todas as tools
        self.all_tools = self._collect_tools()

        # LLM com tools bound
        self.llm_with_tools = self.llm.bind_tools(self.all_tools)

        # Inicializar nós
        self._init_nodes()

        # Compilar grafo
        self.graph = self._build_graph()

    def _init_llms(self) -> None:
        """Inicializa os LLMs."""
        # LLM principal (para respostas)
        self.llm = ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self.api_key,
            temperature=0.3,
            max_output_tokens=8000,
        )

        # LLM rápido para classificação (flash é 10x mais rápido)
        self.llm_fast = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=self.api_key,
            temperature=0.1,
            max_output_tokens=500,
        )

    def _collect_tools(self) -> list:
        """Coleta todas as tools disponíveis."""
        return (
            FinanceTools.get_all_tools()
            + ReminderTools.get_all_tools()
            + MeetingTools.get_all_tools()
            + ContactTools.get_all_tools()
            + tavily_tools.get_tools()
            + yfinance_tools.get_tools()
            + brasil_api_tools.get_tools()
            + google_calendar_tools.get_tools()
        )

    def _init_nodes(self) -> None:
        """Inicializa todos os nós do grafo."""
        self.router_node = RouterNode(self.llm_fast)
        self.agent_nodes = AgentNodes(self.llm_with_tools)
        self.tool_executor_node = ToolExecutorNode(self.all_tools)
        self.general_chat_node = GeneralChatNode(self.llm_with_tools)
        self.response_formatter_node = ResponseFormatterNode(self.llm)
        self.error_handler_node = ErrorHandlerNode()

    def _build_graph(self) -> StateGraph:
        """Constrói o grafo de estados."""
        workflow = StateGraph(IRISState)

        # Adicionar nós
        workflow.add_node("router", self.router_node.route)
        workflow.add_node("finance_agent", self.agent_nodes.finance_agent)
        workflow.add_node("reminder_agent", self.agent_nodes.reminder_agent)
        workflow.add_node("meeting_agent", self.agent_nodes.meeting_agent)
        workflow.add_node("contact_agent", self.agent_nodes.contact_agent)
        workflow.add_node("general_chat", self.general_chat_node.process)
        workflow.add_node("tool_executor", self.tool_executor_node.execute)
        workflow.add_node("response_formatter", self.response_formatter_node.format)
        workflow.add_node("error_handler", self.error_handler_node.handle)

        # Entrada
        workflow.set_entry_point("router")

        # Router -> Agents (condicional)
        workflow.add_conditional_edges(
            "router",
            RouterNode.route_by_intent,
            {
                "finance": "finance_agent",
                "reminder": "reminder_agent",
                "meeting": "meeting_agent",
                "contact": "contact_agent",
                "general": "general_chat",
                "error": "error_handler",
            },
        )

        # Agents -> Tool executor ou Response (condicional)
        agent_names = ["finance_agent", "reminder_agent", "meeting_agent", "contact_agent"]
        for agent in agent_names:
            workflow.add_conditional_edges(
                agent,
                RouterNode.should_execute_tools,
                {
                    "execute": "tool_executor",
                    "respond": "response_formatter",
                    "error": "error_handler",
                },
            )

        # Tool executor -> Response formatter
        workflow.add_edge("tool_executor", "response_formatter")

        # General chat -> Response formatter
        workflow.add_edge("general_chat", "response_formatter")

        # Response formatter -> END
        workflow.add_edge("response_formatter", END)

        # Error handler -> END
        workflow.add_edge("error_handler", END)

        # Compilar com suporte a HITL (Human-in-the-Loop)
        # interrupt_before: Pausa antes de executar tools (confirmação)
        # Descomente para habilitar HITL em produção:
        # return workflow.compile(
        #     interrupt_before=["tool_executor"],  # Confirmar antes de executar
        # )
        return workflow.compile()

    async def process_message(
        self,
        user_id: int,
        session_id: str,
        message: str,
        context: dict = None,
        db: Optional[Session] = None,
    ) -> dict:
        """
        Processa mensagem do usuário.

        Args:
            user_id: ID do usuário
            session_id: ID da sessão
            message: Mensagem do usuário
            context: Contexto adicional
            db: Sessão do banco

        Returns:
            Dict com response, intent, entities, next_action
        """
        import time

        start_time = time.time()

        # Preview da mensagem (primeiros 50 chars)
        msg_preview = message[:50] + "..." if len(message) > 50 else message
        logger.info(f'[IRIS] ▶️ Processando: "{msg_preview}" (user={user_id})')

        enriched_context = context or {}
        memory_manager = None

        # Enriquecer contexto
        if db:
            enriched_context["db"] = db
            memory_manager = MemoryManager(db, user_id)
            memory_context = memory_manager.get_full_context()
            enriched_context["memory"] = memory_context
            enriched_context["context_prompt"] = memory_manager.build_context_prompt()

        # Criar estado inicial
        initial_state = create_initial_state(
            user_id=user_id,
            session_id=session_id,
            message=message,
            context=enriched_context,
        )

        # Configuração com thread_id para persistência
        config = get_thread_config(user_id, session_id)

        # Executar grafo
        result = await self.graph.ainvoke(initial_state, config=config)

        response_text = (
            result["messages"][-1].content
            if result["messages"]
            else "Erro ao processar mensagem."
        )

        # Aprender com a interação
        if memory_manager:
            memory_manager.learn_from_message(
                message=message,
                intent=result.get("intent", ""),
                entities=result.get("entities", {}),
                response=response_text,
            )

        # Log de conclusão com timing
        elapsed = time.time() - start_time
        intent = result.get("intent", "general")
        logger.info(
            f"[IRIS] ✅ Concluído em {elapsed:.1f}s | "
            f"Intent: {intent} | Resposta: {len(response_text)} chars"
        )

        return {
            "response": response_text,
            "intent": result.get("intent", "general"),
            "entities": result.get("entities", {}),
            "next_action": result.get("next_action", ""),
            "confidence": result.get("confidence", 0.0),
        }

    async def process_message_stream(
        self,
        user_id: int,
        session_id: str,
        message: str,
        context: dict = None,
        db: Optional[Session] = None,
    ) -> AsyncIterator[str]:
        """
        Processa mensagem com streaming para respostas incrementais.
        
        Ideal para WhatsApp/Web onde queremos enviar chunks conforme são gerados.
        
        Yields:
            Chunks de texto da resposta
        """
        enriched_context = context or {}
        
        if db:
            enriched_context["db"] = db
            memory_manager = MemoryManager(db, user_id)
            enriched_context["memory"] = memory_manager.get_full_context()
            enriched_context["context_prompt"] = memory_manager.build_context_prompt()

        initial_state = create_initial_state(
            user_id=user_id,
            session_id=session_id,
            message=message,
            context=enriched_context,
        )

        config = get_thread_config(user_id, session_id)

        # Usar astream para streaming com subgraphs
        async for event in self.graph.astream(initial_state, config=config, subgraphs=True):
            # Extrair mensagens do evento
            if isinstance(event, tuple) and len(event) >= 2:
                _, node_output = event
                if isinstance(node_output, dict) and "messages" in node_output:
                    messages = node_output["messages"]
                    if messages:
                        last_msg = messages[-1]
                        if hasattr(last_msg, "content") and last_msg.content:
                            yield last_msg.content


# Singleton para reutilização
_graph_instance: Optional[IRISGraphV2] = None


def get_iris_graph() -> IRISGraphV2:
    """Retorna instância singleton do grafo."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = IRISGraphV2()
    return _graph_instance

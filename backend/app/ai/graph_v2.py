"""
Grafo LangGraph v2 - IRIS com melhores práticas.

Melhorias implementadas:
- Estado tipado herdando de MessagesState
- Tools com Pydantic schemas
- Persistência com PostgreSQL Checkpointer
- Proteção contra loops infinitos
- Separação clara: LLM decide, ToolNode executa
"""

import json
import logging
from datetime import datetime
from typing import List, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from sqlalchemy.orm import Session

from app.ai.agents.prompts.classifier_prompts import ClassifierPrompts
from app.ai.agents.prompts.response_prompts import ResponsePrompts
from app.ai.checkpointer import get_thread_config
from app.ai.memory import MemoryManager
from app.ai.state import IRISState, UserContext, create_initial_state
from app.ai.tools.contact_tools import ContactTools
from app.ai.tools.finance_tools import FinanceTools
from app.ai.tools.meeting_tools import MeetingTools
from app.ai.tools.reminder_tools import ReminderTools
from app.config import settings
from app.core.llm_optimizer import get_optimizer

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

        # LLM principal
        self.llm = ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self.api_key,
            temperature=0.3,
            max_output_tokens=15000,
        )

        # Coletar todas as tools
        self.all_tools = (
            FinanceTools.get_all_tools()
            + ReminderTools.get_all_tools()
            + MeetingTools.get_all_tools()
            + ContactTools.get_all_tools()
        )

        # LLM com tools bound
        self.llm_with_tools = self.llm.bind_tools(self.all_tools)

        # Compilar grafo
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Constrói o grafo de estados."""
        workflow = StateGraph(IRISState)

        # Nós principais
        workflow.add_node("router", self._router_node)
        workflow.add_node("finance_agent", self._finance_agent_node)
        workflow.add_node("reminder_agent", self._reminder_agent_node)
        workflow.add_node("meeting_agent", self._meeting_agent_node)
        workflow.add_node("contact_agent", self._contact_agent_node)
        workflow.add_node("general_chat", self._general_chat_node)
        workflow.add_node("tool_executor", self._tool_executor_node)
        workflow.add_node("response_formatter", self._response_formatter_node)
        workflow.add_node("error_handler", self._error_handler_node)

        # Entrada
        workflow.set_entry_point("router")

        # Router -> Agents (condicional)
        workflow.add_conditional_edges(
            "router",
            self._route_by_intent,
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
        for agent in ["finance_agent", "reminder_agent", "meeting_agent", "contact_agent"]:
            workflow.add_conditional_edges(
                agent,
                self._should_execute_tools,
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

        return workflow.compile()

    def _router_node(self, state: IRISState) -> IRISState:
        """
        Nó Router: classifica intenção e roteia.
        Implementa proteção contra loops.
        """
        # Proteção contra loops
        state["step_count"] = state.get("step_count", 0) + 1
        if state["step_count"] > state.get("max_steps", 15):
            state["error"] = "Limite de passos atingido"
            state["intent"] = "error"
            return state

        last_message = state["messages"][-1]
        optimizer = get_optimizer()

        # Tentar classificação rápida (sem LLM)
        use_fast, fast_intent = optimizer.should_use_fast_classification(last_message.content)
        if use_fast and fast_intent:
            state["intent"] = fast_intent
            state["confidence"] = 0.85
            logger.info(f"Fast classification: {fast_intent}")
            return state

        # Classificação com LLM
        user_ctx = state.get("user_context") or {}
        is_audio = user_ctx.is_audio if isinstance(user_ctx, UserContext) else False

        classification_prompt = ClassifierPrompts.get_classification_prompt(
            conversation_history=self._format_conversation(state),
            message=last_message.content,
            audio_hint=ClassifierPrompts.get_audio_hint(len(last_message.content)) if is_audio else "",
        )

        optimizer.track_call()
        response = self.llm.invoke(classification_prompt)

        try:
            json_start = response.content.find("{")
            json_end = response.content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                classification = json.loads(response.content[json_start:json_end])
                state["intent"] = classification.get("intent", "general")
                state["confidence"] = classification.get("confidence", 0.5)
                state["entities"] = classification.get("entities", {})
            else:
                state["intent"] = "general"
                state["confidence"] = 0.5
        except Exception as e:
            logger.error(f"Erro na classificação: {e}")
            state["intent"] = "general"
            state["confidence"] = 0.3

        logger.info(f"Intent classificado: {state['intent']} (conf: {state['confidence']:.2f})")
        return state

    def _route_by_intent(self, state: IRISState) -> str:
        """Determina próximo nó baseado na intenção."""
        if state.get("error"):
            return "error"
        return state.get("intent", "general")

    def _should_execute_tools(self, state: IRISState) -> str:
        """Decide se deve executar tools ou responder."""
        if state.get("error"):
            return "error"

        # Se há tool_calls pendentes, executar
        if state.get("tool_calls"):
            return "execute"

        return "respond"

    def _finance_agent_node(self, state: IRISState) -> IRISState:
        """Agente de finanças usando tools."""
        return self._process_with_tools(state, "finance")

    def _reminder_agent_node(self, state: IRISState) -> IRISState:
        """Agente de lembretes usando tools."""
        return self._process_with_tools(state, "reminder")

    def _meeting_agent_node(self, state: IRISState) -> IRISState:
        """Agente de reuniões usando tools."""
        return self._process_with_tools(state, "meeting")

    def _contact_agent_node(self, state: IRISState) -> IRISState:
        """Agente de contatos usando tools."""
        return self._process_with_tools(state, "contact")

    def _process_with_tools(self, state: IRISState, domain: str) -> IRISState:
        """
        Processa mensagem usando LLM com tools.
        O LLM decide qual tool chamar, ToolNode executa.
        """
        last_message = state["messages"][-1]

        # System prompt específico do domínio
        system_prompts = {
            "finance": "Você é um assistente especializado em finanças pessoais. Use as tools disponíveis para registrar gastos, receitas ou consultar histórico financeiro.",
            "reminder": "Você é um assistente especializado em lembretes. Use as tools para criar, listar ou deletar lembretes.",
            "meeting": "Você é um assistente especializado em reuniões. Use as tools para agendar ou listar reuniões.",
            "contact": "Você é um assistente especializado em contatos. Use as tools para adicionar ou listar contatos.",
        }

        messages = [SystemMessage(content=system_prompts.get(domain, "")), last_message]

        # Chamar LLM com tools
        response = self.llm_with_tools.invoke(messages)

        # Verificar se há tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            state["tool_calls"] = response.tool_calls
            logger.info(f"Tools chamadas: {[tc['name'] for tc in response.tool_calls]}")
        else:
            # Resposta direta sem tool
            state["messages"] = list(state["messages"]) + [response]

        return state

    def _tool_executor_node(self, state: IRISState) -> IRISState:
        """
        Executa as tools chamadas pelo LLM.
        Separação clara: LLM decide, este nó executa.
        """
        tool_calls = state.get("tool_calls", [])
        tool_results = []

        for tc in tool_calls:
            tool_name = tc.get("name", "")
            tool_args = tc.get("args", {})

            try:
                # Encontrar e executar a tool
                for tool in self.all_tools:
                    if tool.name == tool_name:
                        result = tool.invoke(tool_args)
                        tool_results.append({"tool": tool_name, "result": result, "success": True})
                        break
            except Exception as e:
                logger.error(f"Erro ao executar tool {tool_name}: {e}")
                tool_results.append({"tool": tool_name, "error": str(e), "success": False})

        state["tool_results"] = tool_results
        state["tool_calls"] = []  # Limpar após execução

        return state

    def _general_chat_node(self, state: IRISState) -> IRISState:
        """Conversa geral sem tools específicas."""
        state["next_action"] = "general_response"
        return state

    def _response_formatter_node(self, state: IRISState) -> IRISState:
        """Formata resposta final para o usuário."""
        user_ctx = state.get("user_context")
        user_name = user_ctx.user_name if user_ctx else ""

        # Se já tem resposta do agente, não precisa formatar
        if state["messages"] and isinstance(state["messages"][-1], AIMessage):
            return state

        # Gerar resposta baseada nos resultados
        tool_results = state.get("tool_results", [])

        if tool_results:
            # Construir resposta baseada nos resultados das tools
            successful = [r for r in tool_results if r.get("success")]
            failed = [r for r in tool_results if not r.get("success")]

            parts = []
            for r in successful:
                result_data = r.get("result", {})
                if result_data.get("status") == "pending_execution":
                    # Tool retornou dados para executar
                    action = result_data.get("action", "")
                    state["next_action"] = action
                    state["entities"] = result_data

            if failed:
                parts.append("Alguns itens não puderam ser processados.")

            # Gerar resposta humanizada
            response_prompt = ResponsePrompts.get_response_generation_prompt(
                user_name=user_name,
                comm_style="",
                context_prompt=state.get("context_prompt", ""),
                next_action=state.get("next_action", ""),
                entities=state.get("entities", {}),
                last_message=state["messages"][-1].content if state["messages"] else "",
            )

            response = self.llm.invoke(response_prompt)
            state["messages"] = list(state["messages"]) + [AIMessage(content=response.content)]
        else:
            # Resposta para chat geral
            response_prompt = ResponsePrompts.get_response_generation_prompt(
                user_name=user_name,
                comm_style="",
                context_prompt=state.get("context_prompt", ""),
                next_action="general_response",
                entities={},
                last_message=state["messages"][-1].content if state["messages"] else "",
            )
            response = self.llm.invoke(response_prompt)
            state["messages"] = list(state["messages"]) + [AIMessage(content=response.content)]

        return state

    def _error_handler_node(self, state: IRISState) -> IRISState:
        """Trata erros de forma amigável."""
        error = state.get("error", "Erro desconhecido")
        logger.error(f"Erro no grafo: {error}")

        error_message = (
            "Desculpe, ocorreu um erro ao processar sua solicitação. "
            "Por favor, tente novamente ou reformule sua mensagem."
        )

        state["messages"] = list(state["messages"]) + [AIMessage(content=error_message)]
        return state

    def _format_conversation(self, state: IRISState) -> str:
        """Formata histórico de conversa."""
        memory_ctx = state.get("memory_context")
        if not memory_ctx:
            return ""

        conversation = memory_ctx.conversation if hasattr(memory_ctx, "conversation") else []
        if not conversation:
            return ""

        lines = []
        for msg in conversation[-5:]:
            role = "Usuário" if msg.get("role") == "user" else "Assistente"
            content = msg.get("content", "")[:150]
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    async def process_message(
        self, user_id: int, session_id: str, message: str, context: dict = None, db: Optional[Session] = None
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
            user_id=user_id, session_id=session_id, message=message, context=enriched_context
        )

        # Configuração com thread_id para persistência
        config = get_thread_config(user_id, session_id)

        # Executar grafo
        result = await self.graph.ainvoke(initial_state, config=config)

        response_text = result["messages"][-1].content if result["messages"] else "Erro ao processar mensagem."

        # Aprender com a interação
        if memory_manager:
            memory_manager.learn_from_message(
                message=message,
                intent=result.get("intent", ""),
                entities=result.get("entities", {}),
                response=response_text,
            )

        return {
            "response": response_text,
            "intent": result.get("intent", "general"),
            "entities": result.get("entities", {}),
            "next_action": result.get("next_action", ""),
            "confidence": result.get("confidence", 0.0),
        }


# Singleton para reutilização
_graph_instance: Optional[IRISGraphV2] = None


def get_iris_graph() -> IRISGraphV2:
    """Retorna instância singleton do grafo."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = IRISGraphV2()
    return _graph_instance

"""
Grafo principal do agente de IA - IRIS (Intelligent Retrieval & Insight System).
Orquestra os agentes especializados e gerencia o fluxo de processamento.
"""

import json
import logging
import operator
from typing import Annotated, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.ai.agents import FinanceAgent, MeetingAgent, ReminderAgent
from app.ai.agents.contact_agent import ContactAgent
from app.ai.agents.prompts.classifier_prompts import ClassifierPrompts
from app.ai.agents.prompts.response_prompts import ResponsePrompts
from app.ai.memory import MemoryManager
from app.core.llm_optimizer import get_optimizer
from app.services.embedding_service import (
    AgentMetricsService,
    ClassificationCacheService,
    EmbeddingService,
)

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_id: int
    session_id: str
    intent: str
    entities: dict
    context: dict
    next_action: str
    confidence: float


class WhatsAppAIAgent:
    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.7,
            max_output_tokens=15000,
        )

        self.reminder_agent = ReminderAgent()
        self.finance_agent = FinanceAgent()
        self.meeting_agent = MeetingAgent()
        self.contact_agent = ContactAgent()

        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        """Cria o grafo de estados do agente"""
        workflow = StateGraph(AgentState)

        # Nós
        workflow.add_node("classifier", self._classify_intent)
        workflow.add_node("reminder_handler", self._handle_reminder)
        workflow.add_node("finance_handler", self._handle_finance)
        workflow.add_node("meeting_handler", self._handle_meeting)
        workflow.add_node("contact_handler", self._handle_contact)
        workflow.add_node("general_chat", self._handle_general_chat)
        workflow.add_node("response_generator", self._generate_response)

        # Entrada
        workflow.set_entry_point("classifier")

        # Edges condicionais
        workflow.add_conditional_edges(
            "classifier",
            self._route_by_intent,
            {
                "reminder": "reminder_handler",
                "finance": "finance_handler",
                "meeting": "meeting_handler",
                "contact": "contact_handler",
                "general": "general_chat",
            },
        )

        # Handlers especializados vão direto para o fim (já geram suas respostas)
        workflow.add_edge("reminder_handler", END)
        workflow.add_edge("finance_handler", END)
        workflow.add_edge("meeting_handler", END)
        workflow.add_edge("contact_handler", END)

        # Apenas general_chat precisa do gerador de resposta
        workflow.add_edge("general_chat", "response_generator")
        workflow.add_edge("response_generator", END)

        return workflow.compile()

    def _classify_intent(self, state: AgentState) -> AgentState:
        """Classifica a intenção da mensagem do usuário com cache e otimização."""
        last_message = state["messages"][-1]
        context = state.get("context", {})
        db = context.get("db")
        optimizer = get_optimizer()

        # Tentar classificação rápida (sem LLM) para padrões óbvios
        use_fast, fast_intent = optimizer.should_use_fast_classification(last_message.content)
        if use_fast and fast_intent:
            state["intent"] = fast_intent
            state["entities"] = {}
            state["confidence"] = 0.85
            logger.info(f"Fast classification usada: {fast_intent}")
            return state

        # Tentar cache primeiro
        if db:
            try:
                cache_service = ClassificationCacheService(db)
                cached = cache_service.get_cached(last_message.content)
                if cached and cached["confidence"] >= 0.8:
                    state["intent"] = cached["intent"]
                    state["entities"] = cached["entities"]
                    state["confidence"] = cached["confidence"]
                    logger.info(f"Cache hit para classificação: {cached['intent']}")
                    return state
            except Exception as e:
                logger.warning(f"Erro ao buscar cache de classificação: {e}")
                db.rollback()

        # Se há um pending_reminder, rotear diretamente para reminder
        if context.get("pending_reminder"):
            state["intent"] = "reminder"
            state["entities"] = {}
            state["confidence"] = 1.0
            logger.info("Roteando para reminder (pending_reminder encontrado)")
            return state

        # Se há um pending_contact, rotear diretamente para contact
        if context.get("pending_contact"):
            state["intent"] = "contact"
            state["entities"] = {}
            state["confidence"] = 1.0
            logger.info("Roteando para contact (pending_contact encontrado)")
            return state

        # Se há um pending_meeting, rotear diretamente para meeting
        if context.get("pending_meeting"):
            state["intent"] = "meeting"
            state["entities"] = {}
            state["confidence"] = 1.0
            logger.info("Roteando para meeting (pending_meeting encontrado)")
            return state

        conversation_history = ""
        memory_context = context.get("memory", {})
        conversation = memory_context.get("conversation", [])

        if conversation:
            history_lines = []
            for msg in conversation[-5:]:
                role = "Usuário" if msg.get("role") == "user" else "Assistente"
                content = msg.get("content", "")[:150]
                intent = msg.get("intent", "")
                if intent:
                    history_lines.append(f"{role} [{intent}]: {content}")
                else:
                    history_lines.append(f"{role}: {content}")
            conversation_history = "\n".join(history_lines)

        # Verificar se é áudio longo (possível reunião)
        is_audio = context.get("is_audio", False)
        message_length = len(last_message.content)
        audio_hint = ClassifierPrompts.get_audio_hint(message_length) if is_audio else ""

        classification_prompt = ClassifierPrompts.get_classification_prompt(
            conversation_history=conversation_history, message=last_message.content, audio_hint=audio_hint
        )

        # Registrar chamada LLM
        optimizer.track_call()
        response = self.llm.invoke(classification_prompt)

        try:
            json_start = response.content.find("{")
            json_end = response.content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                classification = json.loads(response.content[json_start:json_end])
            else:
                classification = {"intent": "general", "entities": {}}

            state["intent"] = classification.get("intent", "general")
            state["entities"] = classification.get("entities", {})
            state["confidence"] = classification.get("confidence", 0.5)

            # Salvar no cache se confiança alta
            if db and state["confidence"] >= 0.7:
                cache_service = ClassificationCacheService(db)
                cache_service.cache_classification(
                    last_message.content, state["intent"], state["confidence"], state["entities"]
                )

            logger.info(f"Intenção classificada: {state['intent']} - {classification.get('reasoning', '')}")
        except Exception as e:
            logger.error(f"Erro ao classificar intenção: {e}")
            state["intent"] = "general"
            state["entities"] = {}

        return state

    def _route_by_intent(self, state: AgentState) -> str:
        """Roteia para o handler apropriado baseado na intenção"""
        return state["intent"]

    async def _handle_reminder_async(self, state: AgentState) -> AgentState:
        """Processa solicitações de lembretes usando agente especializado."""
        last_message = state["messages"][-1]

        result = await self.reminder_agent.process(message=last_message.content, context=state.get("context", {}))

        state["entities"] = result.get("entities", {})
        state["next_action"] = result.get("next_action", "")
        state["confidence"] = result.get("confidence", 0.0)
        state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]

        return state

    def _handle_reminder(self, state: AgentState) -> AgentState:
        """Handler síncrono para lembretes."""
        last_message = state["messages"][-1]
        context = state.get("context", {})
        context["user_id"] = state.get("user_id")

        try:
            result = self.reminder_agent.process_sync(message=last_message.content, context=context)

            state["entities"] = result.get("entities", {})
            state["next_action"] = result.get("next_action", "")
            state["confidence"] = result.get("confidence", 0.0)
            state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]
        except Exception as e:
            logger.error(f"Erro no reminder handler: {e}")
            state["messages"] = list(state["messages"]) + [
                AIMessage(content="Desculpe, ocorreu um erro ao processar seu lembrete.")
            ]

        return state

    async def _handle_finance_async(self, state: AgentState) -> AgentState:
        """Processa transações financeiras usando agente especializado."""
        last_message = state["messages"][-1]
        context = state.get("context", {})

        # Garantir que db e user_id estejam no contexto para consultas
        context["user_id"] = state.get("user_id")

        result = await self.finance_agent.process(message=last_message.content, context=context)

        state["entities"] = result.get("entities", {})
        state["next_action"] = result.get("next_action", "")
        state["confidence"] = result.get("confidence", 0.0)
        state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]

        return state

    def _handle_finance(self, state: AgentState) -> AgentState:
        """Handler síncrono para finanças."""
        last_message = state["messages"][-1]
        context = state.get("context", {})
        context["user_id"] = state.get("user_id")

        # Debug: verificar se db está no contexto
        logger.info(
            f"Finance handler - user_id: {context.get('user_id')}, db presente: {context.get('db') is not None}"
        )

        try:
            result = self.finance_agent.process_sync(message=last_message.content, context=context)

            state["entities"] = result.get("entities", {})
            state["next_action"] = result.get("next_action", "")
            state["confidence"] = result.get("confidence", 0.0)
            state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]
        except Exception as e:
            logger.error(f"Erro no finance handler: {e}")
            state["messages"] = list(state["messages"]) + [
                AIMessage(content="Desculpe, ocorreu um erro ao processar sua solicitação financeira.")
            ]

        return state

    async def _handle_meeting_async(self, state: AgentState) -> AgentState:
        """Processa reuniões usando agente especializado."""
        last_message = state["messages"][-1]

        result = await self.meeting_agent.process(message=last_message.content, context=state.get("context", {}))

        state["entities"] = result.get("entities", {})
        state["next_action"] = result.get("next_action", "")
        state["confidence"] = result.get("confidence", 0.0)
        state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]

        return state

    def _handle_meeting(self, state: AgentState) -> AgentState:
        """Handler síncrono para reuniões."""
        last_message = state["messages"][-1]
        context = state.get("context", {})

        try:
            result = self.meeting_agent.process_sync(message=last_message.content, context=context)

            state["entities"] = result.get("entities", {})
            state["next_action"] = result.get("next_action", "")
            state["confidence"] = result.get("confidence", 0.0)
            state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]
        except Exception as e:
            logger.error(f"Erro no meeting handler: {e}")
            state["messages"] = list(state["messages"]) + [
                AIMessage(content="Desculpe, ocorreu um erro ao processar a reunião.")
            ]

        return state

    def _handle_contact(self, state: AgentState) -> AgentState:
        """Handler síncrono para contatos."""
        last_message = state["messages"][-1]
        context = state.get("context", {})
        context["user_id"] = state.get("user_id")

        try:
            result = self.contact_agent.process(message=last_message.content, context=context)

            state["entities"] = result.get("entities", {})
            state["next_action"] = result.get("next_action", "")
            state["confidence"] = result.get("confidence", 0.0)
            state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]
        except Exception as e:
            logger.error(f"Erro no contact handler: {e}")
            state["messages"] = list(state["messages"]) + [
                AIMessage(content="Desculpe, ocorreu um erro ao processar o contato.")
            ]

        return state

    def _handle_general_chat(self, state: AgentState) -> AgentState:
        """Lida com conversas gerais"""
        state["next_action"] = "general_response"
        return state

    def _get_communication_style_prompt(self, memory: dict) -> str:
        """Gera instruções de estilo de comunicação baseado no comportamento do usuário."""
        return ResponsePrompts.get_communication_style_prompt(memory)

    def _generate_response(self, state: AgentState) -> AgentState:
        """Gera a resposta final para o usuário"""
        context = state.get("context", {})
        user_name = context.get("user_name", "")
        context_prompt = context.get("context_prompt", "")
        memory = context.get("memory", {})

        # Extrair primeiro nome para saudações mais naturais
        user_name.split()[0] if user_name else ""

        # Obter estilo de comunicação do usuário
        comm_style = self._get_communication_style_prompt(memory)

        last_msg_content = state["messages"][-1].content if state["messages"] else "N/A"

        response_prompt = ResponsePrompts.get_response_generation_prompt(
            user_name=user_name,
            comm_style=comm_style,
            context_prompt=context_prompt,
            next_action=state["next_action"],
            entities=state["entities"],
            last_message=last_msg_content,
        )

        response = self.llm.invoke(response_prompt)
        state["messages"].append(AIMessage(content=response.content))

        return state

    async def process_message(
        self, user_id: int, session_id: str, message: str, context: dict = None, db: Optional[Session] = None
    ) -> dict:
        """
        Processa uma mensagem do usuário com suporte a memória.

        Args:
            user_id: ID do usuário
            session_id: ID da sessão
            message: Mensagem do usuário
            context: Contexto adicional
            db: Sessão do banco (opcional, para memória)

        Returns:
            Dict com response, intent, entities, next_action
        """
        enriched_context = context or {}
        memory_manager = None

        # Passar db no contexto para agentes que precisam consultar o banco
        if db:
            enriched_context["db"] = db
            enriched_context["user_id"] = user_id

            memory_manager = MemoryManager(db, user_id)
            memory_context = memory_manager.get_full_context()

            enriched_context["memory"] = memory_context
            enriched_context["context_prompt"] = memory_manager.build_context_prompt()

            # RAG: Buscar documentos relevantes usando embeddings
            try:
                embedding_service = EmbeddingService(db)
                rag_context = embedding_service.get_relevant_context(user_id, message, max_tokens=1500)
                if rag_context:
                    enriched_context["rag_context"] = rag_context
                    enriched_context["context_prompt"] += f"\n\n{rag_context}"
            except Exception as e:
                logger.warning(f"Erro ao buscar RAG context: {e}")
                # Rollback para limpar transação com erro
                db.rollback()

            facts = memory_context.get("facts", {})
            if facts.get("name") and not enriched_context.get("user_name"):
                enriched_context["user_name"] = facts["name"]

            # Recuperar pending_reminder da memória (se existir)
            pending_reminder = memory_manager.service.get_memory(user_id, "pending_reminder")
            if pending_reminder:
                enriched_context["pending_reminder"] = pending_reminder

            # Recuperar pending_contact da memória (se existir)
            pending_contact = memory_manager.service.get_memory(user_id, "pending_contact")
            if pending_contact:
                enriched_context["pending_contact"] = pending_contact

            # Recuperar pending_meeting da memória (se existir)
            pending_meeting = memory_manager.service.get_memory(user_id, "pending_meeting")
            if pending_meeting:
                enriched_context["pending_meeting"] = pending_meeting

        initial_state = AgentState(
            messages=[HumanMessage(content=message)],
            user_id=user_id,
            session_id=session_id,
            intent="",
            entities={},
            context=enriched_context,
            next_action="",
            confidence=0.0,
        )

        result = await self.graph.ainvoke(initial_state)

        response_text = result["messages"][-1].content

        if memory_manager:
            memory_manager.learn_from_message(
                message=message, intent=result["intent"], entities=result["entities"], response=response_text
            )

            # Salvar pending_reminder na memória se estamos aguardando tempo
            if result["next_action"] == "await_remind_time":
                pending = result["entities"].get("pending_reminder") or result["entities"].get("pending_reminders")
                if pending:
                    memory_manager.service.set_memory(user_id, "pending_reminder", pending)
            elif result["next_action"] == "create_reminder":
                # Limpar pending_reminder após criar
                memory_manager.service.set_memory(user_id, "pending_reminder", None)

            # Salvar pending_contact na memória se estamos aguardando nome/telefone
            if result["next_action"] in ("await_contact_name", "await_contact_phone"):
                pending = result["entities"].get("pending_contact")
                if pending:
                    memory_manager.service.set_memory(user_id, "pending_contact", pending)
            elif result["next_action"] == "create_contact":
                # Limpar pending_contact após criar
                memory_manager.service.set_memory(user_id, "pending_contact", None)

            # Salvar pending_meeting na memória se estamos aguardando confirmação
            if result["next_action"] in ("await_meeting_time", "await_clarification") and result["entities"].get(
                "pending_meeting"
            ):
                memory_manager.service.set_memory(user_id, "pending_meeting", result["entities"]["pending_meeting"])
            elif result["next_action"] == "create_meeting":
                # Limpar pending_meeting após criar
                memory_manager.service.set_memory(user_id, "pending_meeting", None)

            if result["next_action"] in ["create_reminder", "create_finance", "create_meeting", "create_contact"]:
                memory_manager.update_after_action(action=result["next_action"], entities=result["entities"])

                # Registrar métrica de sucesso
                try:
                    metrics_service = AgentMetricsService(db)
                    agent_map = {
                        "create_reminder": "ReminderAgent",
                        "create_finance": "FinanceAgent",
                        "create_meeting": "MeetingAgent",
                        "create_contact": "ContactAgent",
                    }
                    metrics_service.log_action(
                        user_id=user_id,
                        agent_name=agent_map.get(result["next_action"], "Unknown"),
                        action_type=result["next_action"],
                        success=True,
                        confidence=result.get("confidence", 0.0),
                    )
                except Exception as e:
                    logger.warning(f"Erro ao registrar métrica: {e}")

        return {
            "response": result["messages"][-1].content,
            "intent": result["intent"],
            "entities": result["entities"],
            "next_action": result["next_action"],
            "confidence": result.get("confidence", 0.0),
        }

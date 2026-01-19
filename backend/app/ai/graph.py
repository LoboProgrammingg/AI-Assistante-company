from typing import TypedDict, Annotated, Sequence, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.orm import Session
import operator
from datetime import datetime
import json
import logging

from app.ai.agents import ReminderAgent, FinanceAgent, MeetingAgent
from app.ai.agents.contact_agent import ContactAgent
from app.ai.memory import MemoryManager
from app.services.embedding_service import (
    EmbeddingService, 
    ClassificationCacheService, 
    AgentMetricsService
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
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.3,
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
            }
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
        """Classifica a intenção da mensagem do usuário com cache."""
        last_message = state["messages"][-1]
        context = state.get("context", {})
        db = context.get("db")
        
        # Tentar cache primeiro
        if db:
            cache_service = ClassificationCacheService(db)
            cached = cache_service.get_cached(last_message.content)
            if cached and cached["confidence"] >= 0.8:
                state["intent"] = cached["intent"]
                state["entities"] = cached["entities"]
                state["confidence"] = cached["confidence"]
                logger.info(f"Cache hit para classificação: {cached['intent']}")
                return state
        
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
        audio_hint = ""
        if is_audio and message_length > 500:
            audio_hint = "\nATENÇÃO: Esta mensagem veio de um ÁUDIO LONGO. Se parecer uma transcrição de reunião ou discussão com múltiplos participantes, classifique como 'meeting'."
        
        classification_prompt = f"""
Você é um assistente especializado em classificar intenções de mensagens.
Analise a mensagem ATUAL do usuário considerando o CONTEXTO da conversa anterior.

HISTÓRICO DA CONVERSA (últimas mensagens):
{conversation_history if conversation_history else "Sem histórico anterior"}

MENSAGEM ATUAL DO USUÁRIO: "{last_message.content[:1000]}"
{audio_hint}

REGRAS DE CLASSIFICAÇÃO:
1. Se o usuário menciona VALORES em reais (R$, reais), PREÇOS ou GASTOS → finance
2. Se menciona HORÁRIO, DATA, AGENDAR, LEMBRAR, compromisso → reminder
3. Se menciona REUNIÃO, TRANSCRIÇÃO, ATAS ou parece uma discussão longa com participantes → meeting
4. Se menciona CONTATO, SALVAR NÚMERO, ADICIONAR PESSOA, TELEFONE de alguém, grupo de pessoas → contact
5. Se é uma CONTINUAÇÃO de uma conversa anterior (ex: "sim", "prossiga", "ok"), 
   MANTENHA a mesma intenção do histórico
6. Apenas classifique como "general" se REALMENTE for conversa casual

Intenções:
- reminder: Agendamentos, lembretes, compromissos, horários
- finance: Gastos, receitas, valores, dinheiro, preços
- meeting: Transcrições de reuniões, resumos de reunião, discussões longas
- contact: Adicionar contatos, salvar números, gerenciar pessoas/grupos
- general: Apenas conversas gerais sem ação específica

Retorne APENAS JSON válido:
{{
    "intent": "reminder|finance|meeting|contact|general",
    "confidence": 0.0-1.0,
    "entities": {{}},
    "reasoning": "breve explicação da classificação"
}}
"""
        
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
                    last_message.content,
                    state["intent"],
                    state["confidence"],
                    state["entities"]
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
        
        result = await self.reminder_agent.process(
            message=last_message.content,
            context=state.get("context", {})
        )
        
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
            result = self.reminder_agent.process_sync(
                message=last_message.content,
                context=context
            )
            
            state["entities"] = result.get("entities", {})
            state["next_action"] = result.get("next_action", "")
            state["confidence"] = result.get("confidence", 0.0)
            state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]
        except Exception as e:
            logger.error(f"Erro no reminder handler: {e}")
            state["messages"] = list(state["messages"]) + [AIMessage(content="Desculpe, ocorreu um erro ao processar seu lembrete.")]
        
        return state
    
    async def _handle_finance_async(self, state: AgentState) -> AgentState:
        """Processa transações financeiras usando agente especializado."""
        last_message = state["messages"][-1]
        context = state.get("context", {})
        
        # Garantir que db e user_id estejam no contexto para consultas
        context["user_id"] = state.get("user_id")
        
        result = await self.finance_agent.process(
            message=last_message.content,
            context=context
        )
        
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
        logger.info(f"Finance handler - user_id: {context.get('user_id')}, db presente: {context.get('db') is not None}")
        
        try:
            result = self.finance_agent.process_sync(
                message=last_message.content,
                context=context
            )
            
            state["entities"] = result.get("entities", {})
            state["next_action"] = result.get("next_action", "")
            state["confidence"] = result.get("confidence", 0.0)
            state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]
        except Exception as e:
            logger.error(f"Erro no finance handler: {e}")
            state["messages"] = list(state["messages"]) + [AIMessage(content="Desculpe, ocorreu um erro ao processar sua solicitação financeira.")]
        
        return state

    async def _handle_meeting_async(self, state: AgentState) -> AgentState:
        """Processa reuniões usando agente especializado."""
        last_message = state["messages"][-1]
        
        result = await self.meeting_agent.process(
            message=last_message.content,
            context=state.get("context", {})
        )
        
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
            result = self.meeting_agent.process_sync(
                message=last_message.content,
                context=context
            )
            
            state["entities"] = result.get("entities", {})
            state["next_action"] = result.get("next_action", "")
            state["confidence"] = result.get("confidence", 0.0)
            state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]
        except Exception as e:
            logger.error(f"Erro no meeting handler: {e}")
            state["messages"] = list(state["messages"]) + [AIMessage(content="Desculpe, ocorreu um erro ao processar a reunião.")]
        
        return state

    def _handle_contact(self, state: AgentState) -> AgentState:
        """Handler síncrono para contatos."""
        last_message = state["messages"][-1]
        context = state.get("context", {})
        context["user_id"] = state.get("user_id")
        
        try:
            result = self.contact_agent.process(
                message=last_message.content,
                context=context
            )
            
            state["entities"] = result.get("entities", {})
            state["next_action"] = result.get("next_action", "")
            state["confidence"] = result.get("confidence", 0.0)
            state["messages"] = list(state["messages"]) + [AIMessage(content=result["response"])]
        except Exception as e:
            logger.error(f"Erro no contact handler: {e}")
            state["messages"] = list(state["messages"]) + [AIMessage(content="Desculpe, ocorreu um erro ao processar o contato.")]
        
        return state
    
    def _handle_general_chat(self, state: AgentState) -> AgentState:
        """Lida com conversas gerais"""
        state["next_action"] = "general_response"
        return state
    
    def _get_communication_style_prompt(self, memory: dict) -> str:
        """Gera instruções de estilo de comunicação baseado no comportamento do usuário."""
        behavior = memory.get("behavior_analysis", {}) if memory else {}
        
        if not behavior or behavior.get("message_count", 0) < 5:
            return "ESTILO DE COMUNICAÇÃO: Seja amigável e equilibrado."
        
        msg_count = behavior.get("message_count", 1)
        emoji_ratio = behavior.get("emoji_usage", 0) / msg_count
        informal_ratio = behavior.get("informal_language", 0) / msg_count
        humor_ratio = behavior.get("humor_detected", 0) / msg_count
        
        style_parts = ["ESTILO DE COMUNICAÇÃO (adaptado ao usuário):"]
        
        # Formalidade
        if informal_ratio > 0.4:
            style_parts.append("- Use linguagem CASUAL e descontraída (o usuário é informal)")
            style_parts.append("- Pode usar gírias leves e abreviações")
        elif informal_ratio > 0.2:
            style_parts.append("- Use linguagem amigável mas equilibrada")
        else:
            style_parts.append("- Mantenha tom profissional mas acolhedor")
        
        # Emojis
        if emoji_ratio > 0.3:
            style_parts.append("- USE emojis nas respostas (o usuário gosta! 😊)")
        elif emoji_ratio > 0.1:
            style_parts.append("- Use emojis moderadamente")
        
        # Humor
        if humor_ratio > 0.2:
            style_parts.append("- Pode adicionar humor leve e piadas (o usuário é bem-humorado)")
        
        # Tamanho de mensagem
        avg_len = behavior.get("avg_message_length", 50)
        if avg_len < 30:
            style_parts.append("- Seja CONCISO (o usuário prefere mensagens curtas)")
        else:
            style_parts.append("- Pode dar respostas mais detalhadas")
        
        # Saudação
        greeting = behavior.get("greeting_style", "formal")
        if greeting == "informal":
            style_parts.append("- Saudações informais: 'E aí', 'Opa', 'Fala!'")
        
        return "\n".join(style_parts)
    
    def _generate_response(self, state: AgentState) -> AgentState:
        """Gera a resposta final para o usuário"""
        context = state.get("context", {})
        user_name = context.get("user_name", "")
        context_prompt = context.get("context_prompt", "")
        memory = context.get("memory", {})
        
        # Extrair primeiro nome para saudações mais naturais
        first_name = user_name.split()[0] if user_name else ""
        
        # Obter estilo de comunicação do usuário
        comm_style = self._get_communication_style_prompt(memory)
        
        response_prompt = f"""
Você é um assistente pessoal brasileiro. Seja como um amigo próximo e de confiança do usuário.

INFORMAÇÕES DO USUÁRIO:
- Nome: {user_name or 'Não informado'}
- Use o primeiro nome "{first_name}" nas saudações

{comm_style}

REGRAS CRÍTICAS:
1. NUNCA invente dados. Use APENAS informações do contexto fornecido.
2. Se uma ação foi solicitada mas NÃO está na lista de "AÇÕES CONFIRMADAS", ela NÃO foi feita ainda.
3. Quando confirmar uma ação, use os dados EXATOS das entidades extraídas.
4. Lembre-se de informações importantes que o usuário compartilhou.
5. NUNCA use identificadores genéricos como "WhatsApp 0370" - use sempre o nome real.
6. Você tem acesso ao histórico financeiro, lembretes e reuniões do usuário - use essas informações quando relevante.

{context_prompt}

ESTADO ATUAL:
- Ação a executar: {state['next_action']}
- Dados extraídos: {json.dumps(state['entities'], ensure_ascii=False)}
- Última mensagem do usuário: {state['messages'][-1].content if state['messages'] else 'N/A'}

INSTRUÇÕES DE RESPOSTA:
- Para saudações: Responda de forma breve e amigável usando o nome.
- Se next_action é "create_finance": confirme o registro com valores exatos.
- Se next_action é "create_reminder": confirme o agendamento com data/hora.
- Se next_action é "await_remind_time": pergunte quanto tempo antes quer ser lembrado.
- Seja conciso, natural e demonstre que conhece o usuário.
- Use os dados financeiros/lembretes para dar contexto quando apropriado.

FORMATAÇÃO OBRIGATÓRIA (WhatsApp):
- Use *texto* para negrito (NÃO use **texto**)
- Use _texto_ para itálico/sublinhado
- Use listas numeradas: 1. item, 2. item
- NUNCA use markdown com ** ou listas com - ou *
- NUNCA use blocos de código ou tabelas

Gere sua resposta:"""
        
        response = self.llm.invoke(response_prompt)
        state["messages"].append(AIMessage(content=response.content))
        
        return state
    
    async def process_message(
        self,
        user_id: int,
        session_id: str,
        message: str,
        context: dict = None,
        db: Optional[Session] = None
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
            confidence=0.0
        )
        
        result = await self.graph.ainvoke(initial_state)
        
        response_text = result["messages"][-1].content
        
        if memory_manager:
            memory_manager.learn_from_message(
                message=message,
                intent=result["intent"],
                entities=result["entities"],
                response=response_text
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
            if result["next_action"] in ("await_meeting_time", "await_clarification") and result["entities"].get("pending_meeting"):
                memory_manager.service.set_memory(user_id, "pending_meeting", result["entities"]["pending_meeting"])
            elif result["next_action"] == "create_meeting":
                # Limpar pending_meeting após criar
                memory_manager.service.set_memory(user_id, "pending_meeting", None)
            
            if result["next_action"] in ["create_reminder", "create_finance", "create_meeting", "create_contact"]:
                memory_manager.update_after_action(
                    action=result["next_action"],
                    entities=result["entities"]
                )
                
                # Registrar métrica de sucesso
                try:
                    metrics_service = AgentMetricsService(db)
                    agent_map = {
                        "create_reminder": "ReminderAgent",
                        "create_finance": "FinanceAgent",
                        "create_meeting": "MeetingAgent",
                        "create_contact": "ContactAgent"
                    }
                    metrics_service.log_action(
                        user_id=user_id,
                        agent_name=agent_map.get(result["next_action"], "Unknown"),
                        action_type=result["next_action"],
                        success=True,
                        confidence=result.get("confidence", 0.0)
                    )
                except Exception as e:
                    logger.warning(f"Erro ao registrar métrica: {e}")
        
        return {
            "response": result["messages"][-1].content,
            "intent": result["intent"],
            "entities": result["entities"],
            "next_action": result["next_action"],
            "confidence": result.get("confidence", 0.0)
        }
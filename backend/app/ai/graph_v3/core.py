"""
IRIS Graph v3 - Grafo principal com sistema de memória PERSISTENTE.

Fluxo completo (6 nós):
1. cognitive_node: Classifica + Extrai + Decide (Flash) - COM MEMÓRIA
2. memory_reader: Busca memórias relevantes (sem LLM)
3. context_builder: Constrói contexto otimizado (sem LLM)
4. executor_node: Executa ação
5. memory_writer: Persiste memórias relevantes (sem LLM)
6. responder_node: Gera resposta complexa (Pro) - COM MEMÓRIA

MEMÓRIA PERSISTENTE:
- Carregada no INÍCIO de cada requisição
- Injetada em TODOS os prompts (cognitive, responder)
- Persistida APÓS cada interação
- Histórico de conversas SEMPRE disponível
"""

import logging
import time
from typing import AsyncIterator, Optional

from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.ai.graph_v3.executors import ExecutorNode
from app.ai.graph_v3.nodes import CognitiveNode, ResponderNode
from app.ai.graph_v3.state import IRISStateV3, create_initial_state_v3
from app.ai.memory import (
    MemoryManager,
    MemoryReaderNode,
    MemoryWriterNode,
    WorkingContextBuilder,
)
from app.config import settings
from app.services.pending_context_service import PendingContextService
from app.services.persistent_memory_service import PersistentMemoryService

logger = logging.getLogger(__name__)


class IRISGraphV3:
    """Grafo LangGraph v3 - Arquitetura otimizada."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self._init_llms()
        self._init_nodes()
        self.graph = self._build_graph()
        logger.info("[IRIS v3] ✅ Grafo inicializado")

    def _init_llms(self) -> None:
        """Inicializa os LLMs."""
        self.llm_flash = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            google_api_key=self.api_key,
            temperature=0.1,
            max_output_tokens=30000,
        )

        self.llm_pro = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=self.api_key,
            temperature=0.7,
            max_output_tokens=30000,
        )

    def _init_nodes(self) -> None:
        """Inicializa os nós do grafo."""
        self.cognitive_node = CognitiveNode(self.llm_flash)
        self.memory_reader = MemoryReaderNode()
        self.context_builder = WorkingContextBuilder()
        self.executor_node = ExecutorNode()
        self.memory_writer = MemoryWriterNode()
        self.responder_node = ResponderNode(self.llm_pro)

    def _build_graph(self) -> StateGraph:
        """
        Constrói o grafo de estados com sistema de memória.

        Fluxo:
        cognitive → memory_reader → context_builder → executor → memory_writer → responder → finalize
        """
        workflow = StateGraph(IRISStateV3)

        # Nós principais
        workflow.add_node("cognitive", self.cognitive_node.process)
        workflow.add_node("memory_reader", self.memory_reader.read)
        workflow.add_node("context_builder", self.context_builder.build)
        workflow.add_node("executor", self.executor_node.execute)
        workflow.add_node("memory_writer", self.memory_writer.write)
        workflow.add_node("responder", self.responder_node.respond)
        workflow.add_node("finalize", self._finalize)

        workflow.set_entry_point("cognitive")

        # Cognitive → Memory Reader (sempre lê memória após classificar intent)
        workflow.add_conditional_edges(
            "cognitive",
            self._route_after_cognitive,
            {
                "memory_reader": "memory_reader",
                "responder": "responder",
                "end": "finalize",
            },
        )

        # Memory Reader → Context Builder
        workflow.add_edge("memory_reader", "context_builder")

        # Context Builder → Executor
        workflow.add_edge("context_builder", "executor")

        # Executor → Memory Writer (sempre escreve após executar)
        workflow.add_edge("executor", "memory_writer")

        # Memory Writer → Responder ou Finalize
        workflow.add_conditional_edges(
            "memory_writer",
            self._route_after_memory_writer,
            {"responder": "responder", "end": "finalize"},
        )

        workflow.add_edge("responder", "finalize")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    @staticmethod
    def _route_after_cognitive(state: IRISStateV3) -> str:
        """Roteamento após cognitive node."""
        action = state.get("action")

        logger.info(f"[ROUTE] Action: {action.action_type if action else 'None'}")

        # Se resposta direta (saudação, etc), vai direto para responder
        if action and action.action_type in ["direct_response", "none"]:
            if state.get("response_template"):
                logger.info("[ROUTE] → end (template pronto)")
                return "end"
            logger.info("[ROUTE] → responder (direct_response)")
            return "responder"

        # Se não tem ação ou é needs_llm_response, também vai para responder
        if not action or action.action_type == "needs_llm_response":
            logger.info("[ROUTE] → responder (needs_llm_response)")
            return "responder"

        # Caso contrário, passa pela memória e executor
        logger.info(f"[ROUTE] → memory_reader (action: {action.action_type})")
        return "memory_reader"

    @staticmethod
    def _route_after_memory_writer(state: IRISStateV3) -> str:
        """Roteamento após memory writer."""
        # Sempre passa pelo responder para gerar respostas inteligentes
        # O ResponderNode usará os dados da execução para gerar respostas contextualizadas
        result = state.get("execution_result")

        # Só pula o responder para templates muito simples (saudações, etc)
        if state.get("early_exit") and state.get("response_template"):
            return "end"

        # Para ações com dados, SEMPRE usar o responder para análise inteligente
        return "responder"

    def _finalize(self, state: IRISStateV3) -> dict:
        """Nó final - garante resposta."""
        if state["messages"] and isinstance(state["messages"][-1], AIMessage):
            return {}

        template = state.get("response_template")
        if template:
            return {"messages": [AIMessage(content=template)]}

        result = state.get("execution_result")
        if result and result.response_template:
            return {"messages": [AIMessage(content=result.response_template)]}

        return {"messages": [AIMessage(content="Processado! Como posso ajudar mais?")]}

    async def process_message(
        self,
        user_id: int,
        session_id: str,
        message: str,
        context: dict = None,
        db: Optional[Session] = None,
    ) -> dict:
        """Processa mensagem do usuário com memória persistente."""
        start_time = time.time()

        msg_preview = message[:80] + "..." if len(message) > 80 else message
        logger.info("=" * 60)
        logger.info(f"[IRIS v3] 🚀 NOVA REQUISIÇÃO")
        logger.info(f"[IRIS v3] 👤 User ID: {user_id} | Session: {session_id[:8]}...")
        logger.info(f'[IRIS v3] 💬 Mensagem: "{msg_preview}"')

        enriched_context = context or {}
        memory_manager = None
        persistent_memory = None
        user_name = enriched_context.get("user_name", "")

        full_user_context = ""
        persistent_memory_context = ""

        if db:
            enriched_context["db"] = db

            # ═══════════════════════════════════════════════════════════════
            # ⏳ CONTEXTO PENDENTE - Verificar se há ação aguardando resposta
            # ═══════════════════════════════════════════════════════════════
            pending_context = None
            try:
                pending_service = PendingContextService(db, user_id)
                pending_context = pending_service.resolve_pending_context(message)
                
                if pending_context:
                    logger.info(f"[IRIS v3] ⏳ CONTEXTO PENDENTE RESOLVIDO!")
                    logger.info(f"[IRIS v3]    Action: {pending_context.get('action_type')}")
                    logger.info(f"[IRIS v3]    Params: {pending_context.get('params')}")
                    enriched_context["pending_context"] = pending_context
                    enriched_context["pending_service"] = pending_service
                    
            except Exception as e:
                logger.warning(f"[IRIS v3] Erro ao verificar contexto pendente: {e}")

            # ═══════════════════════════════════════════════════════════════
            # 🧠 MEMÓRIA PERSISTENTE - Carregada PRIMEIRO
            # ═══════════════════════════════════════════════════════════════
            try:
                persistent_memory = PersistentMemoryService(db, user_id)
                
                # Carregar TODA a memória do usuário
                full_memory = persistent_memory.load_full_memory()
                
                # Construir contexto formatado para prompts
                persistent_memory_context = persistent_memory.build_memory_context()
                
                # Guardar no contexto para uso em todos os agentes
                enriched_context["persistent_memory"] = full_memory
                enriched_context["persistent_memory_context"] = persistent_memory_context
                enriched_context["memory_service"] = persistent_memory
                
                # Obter nome do usuário da memória se não foi fornecido
                if not user_name:
                    user_name = persistent_memory.get_user_name()
                    enriched_context["user_name"] = user_name
                
                memory_counts = persistent_memory.count_memories()
                logger.info(f"[IRIS v3] 🧠 Memória persistente carregada:")
                logger.info(f"[IRIS v3]    📝 Preferências: {memory_counts['preferences']}")
                logger.info(f"[IRIS v3]    📋 Fatos: {memory_counts['facts']}")
                logger.info(f"[IRIS v3]    ⚠️ Restrições: {memory_counts['constraints']}")
                logger.info(f"[IRIS v3]    💬 Histórico: {memory_counts['conversation_history']} msgs")
                
            except Exception as e:
                logger.error(f"[IRIS v3] ❌ Erro ao carregar memória persistente: {e}", exc_info=True)
                enriched_context["persistent_memory"] = {}
                enriched_context["persistent_memory_context"] = ""

            # ═══════════════════════════════════════════════════════════════
            # 📊 CONTEXTO DE DADOS (Finanças, Lembretes, etc)
            # ═══════════════════════════════════════════════════════════════
            try:
                from app.ai.context import ContextBuilder

                context_builder = ContextBuilder(db, user_id, user_name)
                full_user_context = context_builder.build_full_context()
                enriched_context["full_user_context"] = full_user_context
                enriched_context["raw_user_data"] = context_builder.get_raw_data()

                raw_data = context_builder.get_raw_data()
                logger.info(f"[IRIS v3] 📊 Contexto de dados: {len(full_user_context)} chars")
                logger.info(
                    f"[IRIS v3]    💰 Transações: {len(raw_data.get('transactions', []))} | "
                    f"⏰ Lembretes: {len(raw_data.get('reminders', {}))}"
                )
            except Exception as e:
                logger.error(f"[IRIS v3] ❌ Erro ao carregar contexto: {e}", exc_info=True)

            # ═══════════════════════════════════════════════════════════════
            # 🔗 COMPATIBILIDADE COM LEGADO (MemoryManager)
            # ═══════════════════════════════════════════════════════════════
            try:
                memory_manager = MemoryManager(db, user_id)
                memory_context = memory_manager.get_full_context()
                enriched_context["memory"] = memory_context
                
                # Combinar memória persistente com context_prompt
                base_prompt = memory_manager.build_context_prompt(user_name=user_name)
                if persistent_memory_context:
                    enriched_context["context_prompt"] = f"{persistent_memory_context}\n\n{base_prompt}"
                else:
                    enriched_context["context_prompt"] = base_prompt
                    
            except Exception as e:
                logger.warning(f"[IRIS v3] Erro no MemoryManager legado: {e}")
                enriched_context["context_prompt"] = persistent_memory_context or ""

            # ═══════════════════════════════════════════════════════════════
            # 💬 HISTÓRICO DE CONVERSAS
            # ═══════════════════════════════════════════════════════════════
            try:
                # Usar histórico da memória persistente se disponível
                if persistent_memory:
                    memory_data = enriched_context.get("persistent_memory", {})
                    conversation_history = memory_data.get("conversation_history", [])
                else:
                    from app.services.memory_service import MemoryService
                    memory_service = MemoryService(db)
                    conversation_history = memory_service.get_conversation_context(user_id, limit=50)

                enriched_context["conversation_history"] = conversation_history or []
                logger.info(f"[IRIS v3] 💬 Histórico: {len(conversation_history)} mensagens")

            except Exception as e:
                logger.warning(f"[IRIS v3] Erro ao carregar histórico: {e}")
                enriched_context["conversation_history"] = []

        # ═══════════════════════════════════════════════════════════════
        # 📦 CONTEXTO FINAL COMBINADO
        # ═══════════════════════════════════════════════════════════════
        combined_context = []
        if persistent_memory_context:
            combined_context.append(persistent_memory_context)
        if full_user_context:
            combined_context.append(full_user_context)
        
        enriched_context["rag_context"] = "\n\n".join(combined_context)

        initial_state = create_initial_state_v3(
            user_id=user_id,
            session_id=session_id,
            message=message,
            user_name=user_name,
            context=enriched_context,
        )

        logger.info(f"[IRIS v3] ⚡ Invocando grafo...")
        result = await self.graph.ainvoke(initial_state)

        response_text = (
            result["messages"][-1].content
            if result["messages"] and isinstance(result["messages"][-1], AIMessage)
            else "Erro ao processar mensagem."
        )

        # ═══════════════════════════════════════════════════════════════
        # 💾 PERSISTIR APRENDIZADO
        # ═══════════════════════════════════════════════════════════════
        if persistent_memory:
            try:
                # Aprender da interação
                persistent_memory.learn_from_interaction(
                    message=message,
                    intent=result.get("intent", ""),
                    entities=result.get("entities", {}),
                    response=response_text,
                )
                logger.debug("[IRIS v3] 💾 Aprendizado persistido")
            except Exception as e:
                logger.warning(f"[IRIS v3] Erro ao persistir aprendizado: {e}")

        # Manter compatibilidade com legado
        if memory_manager:
            try:
                memory_manager.learn_from_message(
                    message=message,
                    intent=result.get("intent", ""),
                    entities=result.get("entities", {}),
                    response=response_text,
                )
            except Exception as e:
                logger.warning(f"[IRIS v3] Erro no aprendizado legado: {e}")

        elapsed = time.time() - start_time

        # Log de resultado final
        logger.info(f"[IRIS v3] ──────────────────────────────")
        logger.info(f"[IRIS v3] ✅ CONCLUÍDO em {elapsed:.2f}s")
        logger.info(
            f"[IRIS v3] 🎯 Intent: {result.get('intent', 'general')} | "
            f"Confidence: {result.get('confidence', 0):.2f}"
        )
        resp_preview = response_text[:100] + "..." if len(response_text) > 100 else response_text
        logger.info(f"[IRIS v3] 📤 Resposta: {resp_preview}")
        logger.info("=" * 60)

        return {
            "response": response_text,
            "intent": result.get("intent", "general"),
            "entities": result.get("entities", {}),
            "confidence": result.get("confidence", 0.0),
            "latency_ms": int(elapsed * 1000),
        }


_graph_instance_v3: Optional[IRISGraphV3] = None


def get_iris_graph_v3() -> IRISGraphV3:
    """Retorna instância singleton do grafo v3."""
    global _graph_instance_v3
    if _graph_instance_v3 is None:
        _graph_instance_v3 = IRISGraphV3()
    return _graph_instance_v3

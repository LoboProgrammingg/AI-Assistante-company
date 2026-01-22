"""
General Chat Node - Chat geral com integrações.

Responsável por:
- Conversas gerais
- Acesso a tools de pesquisa (Tavily)
- Acesso a tools de investimentos (yFinance)
- Acesso a Brasil API e Google Calendar
- Integração com RAG
"""

import logging
from typing import TYPE_CHECKING

from langchain_core.messages import SystemMessage

from app.ai.datetime_utils import get_datetime_context
from app.ai.state import IRISState

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class GeneralChatNode:
    """Nó para chat geral com acesso a integrações."""

    def __init__(self, llm_with_tools: "ChatGoogleGenerativeAI"):
        """
        Args:
            llm_with_tools: LLM com tools vinculadas
        """
        self.llm_with_tools = llm_with_tools

    def process(self, state: IRISState) -> IRISState:
        """
        Processa chat geral com acesso a tools de pesquisa e consulta.
        Inclui: Web Search, Investimentos, Brasil API, Google Calendar.
        """
        last_message = state["messages"][-1]

        # Busca semântica nos documentos do usuário (RAG)
        rag_context = self._get_rag_context(state, last_message.content)
        if rag_context:
            state["rag_context"] = rag_context

        # Contexto de data/hora atual
        datetime_context = get_datetime_context()

        # System prompt com acesso às tools de pesquisa e consulta
        system_prompt = self._build_system_prompt(datetime_context, rag_context)

        messages = [SystemMessage(content=system_prompt), last_message]

        # Usar LLM com tools para poder acessar pesquisa, investimentos, etc.
        response = self.llm_with_tools.invoke(messages)

        # Verificar se há tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            state["tool_calls"] = response.tool_calls
            logger.info(f"[GENERAL] 🛠️ Tools: {[tc['name'] for tc in response.tool_calls]}")
        else:
            state["messages"] = list(state["messages"]) + [response]

        state["next_action"] = "general_response"
        return state

    def _build_system_prompt(self, datetime_context: str, rag_context: str) -> str:
        """Constrói o prompt de sistema para chat geral."""
        return f"""Você é IRIS, assistente pessoal inteligente.

📅 DATA/HORA ATUAL: {datetime_context}

SUAS CAPACIDADES ESPECIAIS:
1. PESQUISA WEB: Use _search_web ou _search_news para buscar informações atualizadas na internet.
2. INVESTIMENTOS: Use _get_stock_price, _get_stock_info, _get_crypto_price, _get_currency_rate para dados financeiros.
   - Ações brasileiras: adicione .SA (ex: PETR4.SA, VALE3.SA)
   - Criptos: BTC, ETH, SOL
   - Câmbio: USD, EUR para BRL
3. BRASIL API:
   - _consultar_cep: Endereço completo por CEP
   - _consultar_clima: Previsão do tempo
   - _listar_feriados: Feriados nacionais
   - _consultar_taxas: Selic, CDI, IPCA
   - _listar_bancos / _consultar_banco: Códigos bancários
   - _consultar_fipe: Preços de veículos
4. GOOGLE CALENDAR: _listar_eventos, _criar_evento, _verificar_disponibilidade

{rag_context}

REGRAS:
- Se o usuário perguntar sobre algo que precisa de dados atualizados, USE as tools.
- Para investimentos, SEMPRE consulte dados reais, NUNCA invente valores.
- Responda de forma natural e útil."""

    def _get_rag_context(self, state: IRISState, message_content: str) -> str:
        """Busca contexto RAG nos documentos do usuário."""
        db = state.get("db")
        user_id = state.get("user_id")

        if not db or not user_id:
            return ""

        try:
            from app.services.embedding_service import EmbeddingService
            embedding_service = EmbeddingService(db)
            rag_context = embedding_service.get_relevant_context(user_id, message_content, max_tokens=2000)
            if rag_context:
                logger.debug(f"[RAG] Contexto geral ({len(rag_context)} chars)")
            return rag_context or ""
        except Exception as e:
            logger.debug(f"[RAG] Sem contexto geral: {e}")
            return ""

"""
Responder Node - Geração de respostas inteligentes via LLM Pro.

Responsabilidade:
- Gerar respostas INTELIGENTES baseadas nos dados REAIS do usuário
- Responder EXATAMENTE o que o usuário perguntou
- Usar contexto financeiro quando necessário
- Agir como ASSESSOR FINANCEIRO SÊNIOR quando aplicável
- NÃO forçar uso de dados quando não forem relevantes

Usa Gemini Pro com orquestração cognitiva.
Implementa retry com backoff exponencial para resiliência.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict

from langchain_core.messages import AIMessage

from app.ai.datetime_utils import get_datetime_context
from app.ai.graph_v3.prompts import GENERAL_PROMPT, RESPONSE_PROMPT
from app.ai.graph_v3.state import IRISStateV3
from app.ai.llm.retry import invoke_llm_with_retry

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class ResponderNode:
    """Gerador de respostas via LLM Pro."""

    def __init__(self, llm: "ChatGoogleGenerativeAI"):
        self.llm = llm

    def respond(self, state: IRISStateV3) -> Dict[str, Any]:
        """Gera resposta usando LLM Pro."""
        template = state.get("response_template")
        if template:
            logger.info("[RESPONDER] ⚡ Usando template existente")
            return {"messages": [AIMessage(content=template)]}

        execution_result = state.get("execution_result")

        if execution_result and not execution_result.response_template:
            return self._respond_with_context(state)

        return self._respond_general(state)

    # ------------------------------------------------------------------
    # RESPONDER COM CONTEXTO DE EXECUÇÃO
    # ------------------------------------------------------------------

    def _respond_with_context(self, state: IRISStateV3) -> Dict[str, Any]:
        user_message = state["messages"][-1].content if state["messages"] else ""
        user_name = state.get("user_name", "")

        # Flags cognitivas (vindas do CognitiveNode)
        needs_user_data = state.get("needs_user_data", False)
        needs_analysis = state.get("needs_analysis", False)

        logger.info(
            f"[RESPONDER] Contextual | needs_user_data={needs_user_data} "
            f"| needs_analysis={needs_analysis}"
        )

        # Construir contexto SOMENTE se necessário
        if needs_user_data:
            data_context = self._build_data_context(state)
        else:
            data_context = (
                "Nenhum dado financeiro pessoal é necessário para responder esta pergunta. "
                "Você pode responder com conhecimento financeiro geral, análise conceitual "
                "ou orientação estratégica."
            )

        advisor_mode = (
            "\n⚠️ MODO ASSESSOR FINANCEIRO SÊNIOR ATIVO\n"
            "Você deve priorizar análise, trade-offs, riscos e contexto de mercado.\n"
            if needs_analysis
            else ""
        )

        prompt = (
            RESPONSE_PROMPT.format(
                datetime_context=get_datetime_context(),
                user_context=f"👤 Usuário: {user_name}" if user_name else "",
                user_message=user_message,
                data_context=data_context,
            )
            + advisor_mode
        )

        try:
            response = invoke_llm_with_retry(
                self.llm,
                prompt,
                operation_name="RESPONDER",
                max_attempts=3
            )
            logger.info(f"[RESPONDER] 💬 Resposta gerada ({len(response.content)} chars)")
            return {"messages": [AIMessage(content=response.content)]}
        except Exception as e:
            logger.error(f"[RESPONDER] ❌ Erro ao gerar resposta: {e}", exc_info=True)
            return {
                "messages": [
                    AIMessage(content="Desculpe, tive um problema ao processar isso. Pode tentar novamente?")
                ]
            }

    # ------------------------------------------------------------------
    # RESPONDER GERAL (CONVERSA / EDUCAÇÃO / ORIENTAÇÃO)
    # ------------------------------------------------------------------

    def _respond_general(self, state: IRISStateV3) -> Dict[str, Any]:
        user_message = state["messages"][-1].content if state["messages"] else ""
        user_name = state.get("user_name", "")

        needs_analysis = state.get("needs_analysis", False)

        logger.info(f"[RESPONDER] General | needs_analysis={needs_analysis}")
        logger.info(f"[RESPONDER] Message: {user_message[:120]}")

        full_context = self._build_full_context(state)

        advisor_mode = (
            "\n⚠️ MODO ASSESSOR FINANCEIRO SÊNIOR ATIVO\n"
            "Você está autorizado a explicar conceitos, analisar cenários e dar orientação estratégica.\n"
            if needs_analysis
            else ""
        )

        prompt = (
            GENERAL_PROMPT.format(
                datetime_context=get_datetime_context(),
                user_context=f"👤 Usuário: {user_name}" if user_name else "",
                full_context=full_context,
                user_message=user_message,
            )
            + advisor_mode
        )

        try:
            response = invoke_llm_with_retry(
                self.llm,
                prompt,
                operation_name="RESPONDER_GENERAL",
                max_attempts=3
            )
            return {"messages": [AIMessage(content=response.content)]}
        except Exception as e:
            logger.error(f"[RESPONDER] ❌ Erro na resposta geral: {e}", exc_info=True)
            return {"messages": [AIMessage(content="Tive um problema, pode repetir?")]}

    # ------------------------------------------------------------------
    # CONTEXTO DE DADOS (FINANCEIRO / EXECUÇÃO)
    # ------------------------------------------------------------------

    def _build_data_context(self, state: IRISStateV3) -> str:
        result = state.get("execution_result")
        entities = state.get("entities", {})
        lines = []

        if result and result.success and result.data:
            data = result.data

            if "transactions" in data:
                txs = data["transactions"]
                lines.append(f"### TRANSAÇÕES ({len(txs)}):")
                for i, t in enumerate(txs[:20], 1):
                    emoji = "🔴" if t.get("type") == "expense" else "🟢"
                    lines.append(
                        f"{i}. {emoji} R$ {t.get('amount', 0):,.2f} - "
                        f"{t.get('description', 'Sem descrição')} "
                        f"({t.get('category', 'Outros')}) - {t.get('date', '')}"
                    )

                if len(txs) > 20:
                    lines.append(f"... e mais {len(txs) - 20} transações")

            if "summary" in data:
                s = data["summary"]
                balance = s.get("balance", 0)
                emoji = "🟢" if balance >= 0 else "🔴"
                lines.extend(
                    [
                        "",
                        "### RESUMO FINANCEIRO:",
                        f"💵 Receitas: R$ {s.get('total_income', 0):,.2f}",
                        f"💸 Gastos: R$ {s.get('total_expenses', 0):,.2f}",
                        f"{emoji} Saldo: R$ {balance:,.2f}",
                        f"📊 Transações: {s.get('count', 0)}",
                    ]
                )

            if "web_search" in data and data["web_search"].get("answer"):
                lines.extend(
                    [
                        "",
                        "### CONTEXTO DA WEB:",
                        data["web_search"]["answer"],
                    ]
                )

        original_msg = entities.get("original_message")
        if original_msg:
            lines.insert(0, f'### PERGUNTA ORIGINAL: "{original_msg}"\n')

        return "\n".join(lines) if lines else "Nenhum dado financeiro relevante foi necessário."

    # ------------------------------------------------------------------
    # CONTEXTO GERAL (MEMÓRIA / PERFIL)
    # ------------------------------------------------------------------

    def _build_full_context(self, state: IRISStateV3) -> str:
        db = state.get("db")
        user_id = state.get("user_id")

        if db and user_id:
            try:
                from app.ai.context import ContextBuilder

                builder = ContextBuilder(db, user_id, state.get("user_name", ""))
                return builder.build_full_context()
            except Exception as e:
                logger.error("[RESPONDER] Erro ao construir contexto completo", exc_info=True)

        context_prompt = state.get("context_prompt", "")
        rag_context = state.get("rag_context", "")

        return (
            f"{context_prompt}\n\n{rag_context}"
            if context_prompt or rag_context
            else "Nenhum contexto adicional disponível."
        )

"""
Error Handler Node - Tratamento de erros.

Responsável por:
- Tratar erros de forma amigável
- Gerar mensagens de erro user-friendly
"""

import logging

from langchain_core.messages import AIMessage

from app.ai.state import IRISState

logger = logging.getLogger(__name__)


class ErrorHandlerNode:
    """Nó responsável pelo tratamento de erros."""

    @staticmethod
    def handle(state: IRISState) -> IRISState:
        """Trata erros de forma amigável."""
        error = state.get("error", "Erro desconhecido")
        logger.error(f"Erro no grafo: {error}")

        error_message = (
            "Desculpe, ocorreu um erro ao processar sua solicitação. "
            "Por favor, tente novamente ou reformule sua mensagem."
        )

        state["messages"] = list(state["messages"]) + [AIMessage(content=error_message)]
        return state

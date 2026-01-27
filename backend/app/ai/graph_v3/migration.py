"""
IRIS Graph v3 - Entry Point.

Módulo principal de processamento de mensagens.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


GRAPH_VERSION = "v3"


async def process_message(
    user_id: int,
    session_id: str,
    message: str,
    context: dict = None,
    db: Optional[Session] = None,
) -> dict:
    """
    Processa mensagem usando o Graph v3.

    Args:
        user_id: ID do usuário
        session_id: ID da sessão
        message: Mensagem do usuário
        context: Contexto adicional
        db: Sessão do banco de dados

    Returns:
        Dict com resposta e metadados
    """
    from app.ai.graph_v3 import get_iris_graph_v3

    graph = get_iris_graph_v3()
    return await graph.process_message(user_id, session_id, message, context, db)


def get_graph_stats() -> dict:
    """Retorna estatísticas do grafo."""
    return {
        "version": GRAPH_VERSION,
        "active": True,
    }

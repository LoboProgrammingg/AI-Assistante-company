"""
Migração do Graph v2 para v3.

Permite rodar ambas as versões em paralelo para testes A/B.
Facilita rollback se necessário.
"""

import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Feature flag para escolher versão
# PADRÃO: v3 (produção)
GRAPH_VERSION = os.getenv("IRIS_GRAPH_VERSION", "v3")  # "v2" ou "v3"


async def process_message(
    user_id: int,
    session_id: str,
    message: str,
    context: dict = None,
    db: Optional[Session] = None,
) -> dict:
    """
    Processa mensagem usando a versão configurada do grafo.
    
    Env: IRIS_GRAPH_VERSION = "v2" | "v3"
    
    Permite migração gradual e testes A/B.
    """
    if GRAPH_VERSION == "v3":
        return await _process_v3(user_id, session_id, message, context, db)
    else:
        return await _process_v2(user_id, session_id, message, context, db)


async def _process_v3(
    user_id: int,
    session_id: str,
    message: str,
    context: dict = None,
    db: Optional[Session] = None,
) -> dict:
    """Processa com Graph v3 (otimizado)."""
    from app.ai.graph_v3 import get_iris_graph_v3
    
    graph = get_iris_graph_v3()
    return await graph.process_message(user_id, session_id, message, context, db)


async def _process_v2(
    user_id: int,
    session_id: str,
    message: str,
    context: dict = None,
    db: Optional[Session] = None,
) -> dict:
    """Processa com Graph v2 (atual)."""
    from app.ai.graph_v2 import get_iris_graph
    
    graph = get_iris_graph()
    return await graph.process_message(user_id, session_id, message, context, db)


def get_graph_stats() -> dict:
    """Retorna estatísticas de uso dos grafos."""
    return {
        "version": GRAPH_VERSION,
        "v3_enabled": GRAPH_VERSION == "v3",
    }


# ==================== COMPARAÇÃO DE PERFORMANCE ====================

async def compare_performance(
    user_id: int,
    session_id: str,
    message: str,
    context: dict = None,
    db: Optional[Session] = None,
) -> dict:
    """
    Executa ambas as versões e compara performance.
    
    Útil para testes antes da migração completa.
    
    ATENÇÃO: Executa DUAS vezes - usar apenas em dev/staging.
    """
    import time
    
    # Executar v2
    start_v2 = time.time()
    result_v2 = await _process_v2(user_id, session_id, message, context, db)
    time_v2 = time.time() - start_v2
    
    # Executar v3
    start_v3 = time.time()
    result_v3 = await _process_v3(user_id, session_id, message, context, db)
    time_v3 = time.time() - start_v3
    
    improvement = ((time_v2 - time_v3) / time_v2) * 100 if time_v2 > 0 else 0
    
    return {
        "v2": {
            "response": result_v2.get("response", "")[:200],
            "intent": result_v2.get("intent"),
            "latency_ms": int(time_v2 * 1000),
        },
        "v3": {
            "response": result_v3.get("response", "")[:200],
            "intent": result_v3.get("intent"),
            "latency_ms": int(time_v3 * 1000),
        },
        "improvement_percent": f"{improvement:.1f}%",
        "winner": "v3" if time_v3 < time_v2 else "v2",
    }

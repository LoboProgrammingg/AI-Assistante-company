"""
Checkpointer para persistência do LangGraph.
Usa PostgreSQL para persistir estado entre conversas.
"""
import logging
from typing import Optional
from contextlib import asynccontextmanager

from app.config import settings

logger = logging.getLogger(__name__)

_checkpointer = None


async def get_postgres_checkpointer():
    """
    Retorna checkpointer PostgreSQL para persistência.
    
    Benefícios:
    - Conversas persistem entre reinícios
    - Pode retomar conversa de dias atrás
    - Histórico completo do fluxo
    """
    global _checkpointer
    
    if _checkpointer is not None:
        return _checkpointer
    
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        
        database_url = settings.get_database_url
        
        # Criar checkpointer
        _checkpointer = AsyncPostgresSaver.from_conn_string(database_url)
        
        # Setup das tabelas (executar apenas na primeira vez)
        await _checkpointer.setup()
        
        logger.info("PostgreSQL Checkpointer inicializado com sucesso")
        return _checkpointer
        
    except ImportError:
        logger.warning(
            "langgraph-checkpoint-postgres não instalado. "
            "Instale com: pip install langgraph-checkpoint-postgres"
        )
        return None
    except Exception as e:
        logger.error(f"Erro ao inicializar PostgreSQL Checkpointer: {e}")
        return None


def get_memory_checkpointer():
    """
    Fallback: Checkpointer em memória (apenas para desenvolvimento).
    Não persiste entre reinícios!
    """
    try:
        from langgraph.checkpoint.memory import MemorySaver
        logger.warning("Usando MemorySaver (não persiste entre reinícios)")
        return MemorySaver()
    except ImportError:
        logger.error("langgraph não instalado corretamente")
        return None


@asynccontextmanager
async def get_checkpointer():
    """
    Context manager para obter checkpointer.
    Tenta PostgreSQL primeiro, fallback para memória.
    """
    checkpointer = await get_postgres_checkpointer()
    
    if checkpointer is None:
        checkpointer = get_memory_checkpointer()
    
    try:
        yield checkpointer
    finally:
        pass


def get_thread_config(user_id: int, session_id: str = None) -> dict:
    """
    Gera configuração de thread para o LangGraph.
    
    Args:
        user_id: ID do usuário
        session_id: ID da sessão (opcional)
        
    Returns:
        Config dict para usar com graph.invoke()
    """
    thread_id = f"user_{user_id}"
    if session_id:
        thread_id = f"{thread_id}_{session_id}"
    
    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": settings.LANGGRAPH_RECURSION_LIMIT,
    }

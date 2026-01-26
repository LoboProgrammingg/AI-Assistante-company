"""
IRIS Memory System - Sistema de memória avançada em camadas.

Arquitetura:
- Camada 1: Sessão (volátil)
- Camada 2: Trabalho (Redis, 24h)
- Camada 3: Longo Prazo (PostgreSQL)
- Camada 4: Episódica (PostgreSQL, rotacionada)

Fluxo no LangGraph:
Input → Cognitive → MemoryReader → ContextBuilder → Executor → MemoryWriter → Response
"""

# MemoryManager
from app.ai.memory.manager import MemoryManager

from app.ai.memory.types import (
    MemoryItem,
    MemoryType,
    MemoryLayer,
    MemorySource,
    Importance,
    MemoryQuery,
    MemoryWriteResult,
    SOURCE_CONFIDENCE,
    MEMORY_LIMITS,
)

from app.ai.memory.reader import (
    MemoryReaderNode,
    read_relevant_memories,
)

from app.ai.memory.writer import (
    MemoryWriterNode,
    write_memory_if_relevant,
)

from app.ai.memory.context_builder import (
    WorkingContextBuilder,
    build_working_context,
    compress_for_llm,
)

from app.ai.memory.redis_working import (
    RedisWorkingMemory,
    get_redis_working_memory,
)

__all__ = [
    # Types
    "MemoryItem",
    "MemoryType",
    "MemoryLayer",
    "MemorySource",
    "Importance",
    "MemoryQuery",
    "MemoryWriteResult",
    "SOURCE_CONFIDENCE",
    "MEMORY_LIMITS",
    # Reader
    "MemoryReaderNode",
    "read_relevant_memories",
    # Writer
    "MemoryWriterNode",
    "write_memory_if_relevant",
    # Context Builder
    "WorkingContextBuilder",
    "build_working_context",
    "compress_for_llm",
    # Redis Working Memory
    "RedisWorkingMemory",
    "get_redis_working_memory",
    # Compatibilidade legada
    "MemoryManager",
]

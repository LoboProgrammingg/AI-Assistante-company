"""
Memory Types - Estruturas de dados para o sistema de memória.

Cada item de memória é estruturado, não texto solto.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MemoryType(Enum):
    """Tipos de memória suportados."""

    # Identidade do Usuário
    PREFERENCE = "preference"  # "Prefiro ser chamado de João"
    HABIT = "habit"  # "Sempre pago contas dia 5"
    RECURRENCE = "recurrence"  # "Academia segundas e quartas"
    CONSTRAINT = "constraint"  # "Alérgico a frutos do mar"
    IDENTITY = "identity"  # "Trabalho como engenheiro"

    # Episódicos
    EVENT = "event"  # "Viajou para SP em janeiro"
    DECISION = "decision"  # "Decidiu investir em X"
    ACTION = "action"  # "Criou lembrete para Y"

    # Contextuais
    CONTEXT = "context"  # Informação temporária
    INFERENCE = "inference"  # Dedução do sistema


class MemoryLayer(Enum):
    """Camadas de memória."""

    SESSION = "session"  # Volátil - conversa atual
    WORKING = "working"  # Semi-persistente - 24h
    LONGTERM = "longterm"  # Persistente - indefinido
    EPISODIC = "episodic"  # Persistente - rotacionado
    ARCHIVED = "archived"  # Arquivado - baixa confiança


class MemorySource(Enum):
    """Origem da memória."""

    USER_EXPLICIT = "user_explicit"  # Usuário disse diretamente
    USER_IMPLICIT = "user_implicit"  # Detectado do comportamento
    INFERENCE = "inference"  # IA deduziu
    SYSTEM = "system"  # Dados do sistema


class Importance(Enum):
    """Nível de importância."""

    LOW = "low"  # Pode expirar após 30 dias
    MEDIUM = "medium"  # Manter por 90 dias
    HIGH = "high"  # Manter por 1 ano
    CRITICAL = "critical"  # Nunca expira automaticamente


# Confiança inicial por fonte
SOURCE_CONFIDENCE = {
    MemorySource.USER_EXPLICIT: 0.9,
    MemorySource.USER_IMPLICIT: 0.7,
    MemorySource.INFERENCE: 0.5,
    MemorySource.SYSTEM: 1.0,
}


@dataclass
class MemoryItem:
    """Item de memória estruturado."""

    # Identificação
    memory_id: str = ""
    user_id: int = 0

    # Classificação
    memory_type: MemoryType = MemoryType.CONTEXT
    layer: MemoryLayer = MemoryLayer.LONGTERM
    category: str = "general"

    # Conteúdo
    key: str = ""
    value: Any = None
    summary: str = ""

    # Metadados de Confiança
    confidence: float = 0.5
    importance: Importance = Importance.MEDIUM
    source: MemorySource = MemorySource.USER_IMPLICIT

    # Temporalidade
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    last_confirmed: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    access_count: int = 0

    # Auditoria
    origin_message_id: str = ""
    origin_session_id: str = ""
    update_history: List[Dict] = field(default_factory=list)

    # Flags
    requires_confirmation: bool = False
    is_sensitive: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "memory_id": self.memory_id,
            "user_id": self.user_id,
            "memory_type": self.memory_type.value,
            "layer": self.layer.value,
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "summary": self.summary,
            "confidence": self.confidence,
            "importance": self.importance.value,
            "source": self.source.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
        }

    def to_context_string(self) -> str:
        """Converte para string de contexto (para LLM)."""
        return self.summary or f"{self.key}: {self.value}"


@dataclass
class MemoryQuery:
    """Query para buscar memórias."""

    user_id: int
    intent: str = ""
    memory_types: List[MemoryType] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    min_confidence: float = 0.5
    max_items: int = 10
    include_expired: bool = False


@dataclass
class MemoryWriteResult:
    """Resultado de operação de escrita."""

    success: bool
    action: str  # "created" | "updated" | "skipped" | "error"
    memory_id: Optional[str] = None
    message: str = ""


# Limites por tipo de memória
MEMORY_LIMITS = {
    MemoryType.PREFERENCE: 50,
    MemoryType.HABIT: 30,
    MemoryType.CONSTRAINT: 20,
    MemoryType.IDENTITY: 10,
    MemoryType.RECURRENCE: 30,
    MemoryType.EVENT: 100,
    MemoryType.ACTION: 500,
    MemoryType.DECISION: 200,
    MemoryType.CONTEXT: 20,
    MemoryType.INFERENCE: 50,
}

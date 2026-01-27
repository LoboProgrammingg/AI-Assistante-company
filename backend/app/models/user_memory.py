"""
Modelo de memória estruturada para o sistema IRIS v3.

Este modelo substitui o uso genérico de ConversationMemory para armazenar
memórias do usuário de forma estruturada, com confiança, importância,
TTL e auditoria completa.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import Base


def utc_now():
    """Retorna datetime atual em UTC."""
    return datetime.now(timezone.utc)


class MemoryTypeEnum(enum.Enum):
    """Tipos de memória suportados."""

    PREFERENCE = "preference"  # "Prefiro ser chamado de João"
    HABIT = "habit"  # "Sempre pago contas dia 5"
    RECURRENCE = "recurrence"  # "Academia segundas e quartas"
    CONSTRAINT = "constraint"  # "Alérgico a frutos do mar"
    IDENTITY = "identity"  # "Trabalho como engenheiro"
    EVENT = "event"  # "Viajou para SP em janeiro"
    DECISION = "decision"  # "Decidiu investir em X"
    ACTION = "action"  # "Criou lembrete para Y"
    CONTEXT = "context"  # Informação temporária
    INFERENCE = "inference"  # Dedução do sistema


class MemoryLayerEnum(enum.Enum):
    """Camadas de memória."""

    SESSION = "session"  # Volátil - conversa atual
    WORKING = "working"  # Semi-persistente - 24h
    LONGTERM = "longterm"  # Persistente - indefinido
    EPISODIC = "episodic"  # Persistente - rotacionado
    ARCHIVED = "archived"  # Arquivado - baixa confiança


class ImportanceEnum(enum.Enum):
    """Nível de importância."""

    LOW = "low"  # Pode expirar após 30 dias
    MEDIUM = "medium"  # Manter por 90 dias
    HIGH = "high"  # Manter por 1 ano
    CRITICAL = "critical"  # Nunca expira automaticamente


class MemorySourceEnum(enum.Enum):
    """Origem da memória."""

    USER_EXPLICIT = "user_explicit"  # Usuário disse diretamente
    USER_IMPLICIT = "user_implicit"  # Detectado do comportamento
    INFERENCE = "inference"  # IA deduziu
    SYSTEM = "system"  # Dados do sistema


class UserMemory(Base):
    """
    Modelo de memória estruturada para o sistema IRIS v3.

    REGRAS DE USO:
    - Sempre filtrar por user_id (isolamento obrigatório)
    - Confidence decai automaticamente via jobs
    - Constraints nunca expiram automaticamente
    - Todas as operações devem ser auditadas
    """

    __tablename__ = "user_memories"

    # ==================== IDENTIFICAÇÃO ====================
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # ==================== CLASSIFICAÇÃO ====================
    memory_type = Column(Enum(MemoryTypeEnum), nullable=False, default=MemoryTypeEnum.CONTEXT, index=True)
    layer = Column(Enum(MemoryLayerEnum), nullable=False, default=MemoryLayerEnum.LONGTERM)
    category = Column(String(50), default="general", index=True)

    # ==================== CONTEÚDO ====================
    key = Column(String(255), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    summary = Column(String(200))  # Resumo para contexto LLM (máx 200 chars)

    # ==================== CONFIANÇA ====================
    confidence = Column(Float, default=0.5, index=True)
    importance = Column(Enum(ImportanceEnum), default=ImportanceEnum.MEDIUM)
    source = Column(Enum(MemorySourceEnum), default=MemorySourceEnum.USER_IMPLICIT)

    # ==================== TEMPORALIDADE ====================
    created_at = Column(DateTime, default=utc_now, index=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    last_accessed = Column(DateTime, default=utc_now, index=True)
    last_confirmed = Column(DateTime)  # Quando foi reforçado pelo usuário
    expires_at = Column(DateTime, index=True)  # TTL
    access_count = Column(Integer, default=0)

    # ==================== AUDITORIA ====================
    origin_session_id = Column(String(100))
    origin_message_id = Column(String(100))

    # ==================== FLAGS ====================
    requires_confirmation = Column(Boolean, default=False)
    is_sensitive = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False, index=True)

    # ==================== RELATIONSHIPS ====================
    user = relationship("User", back_populates="memories")
    audit_logs = relationship("MemoryAuditLog", back_populates="memory", cascade="all, delete-orphan")

    # ==================== ÍNDICES COMPOSTOS ====================
    __table_args__ = (
        # Query principal: memórias por usuário, tipo e confiança
        Index("idx_um_user_type_conf", "user_id", "memory_type", "confidence"),
        # Query por categoria
        Index("idx_um_user_category", "user_id", "category"),
        # Query por camada
        Index("idx_um_user_layer", "user_id", "layer"),
        # Job de expiração
        Index("idx_um_expires", "expires_at", "is_archived"),
        # Job de decay
        Index("idx_um_decay", "last_accessed", "confidence", "is_archived"),
        # Unique constraint: evita duplicatas por user+key
        Index("idx_um_user_key", "user_id", "key", unique=True),
    )

    def to_dict(self) -> dict:
        """Converte para dicionário (para auditoria)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type.value if self.memory_type else None,
            "layer": self.layer.value if self.layer else None,
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "summary": self.summary,
            "confidence": self.confidence,
            "importance": self.importance.value if self.importance else None,
            "source": self.source.value if self.source else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "is_archived": self.is_archived,
        }

    def to_context_string(self) -> str:
        """Converte para string de contexto (para LLM)."""
        return self.summary or str(self.value)[:100]

    def __repr__(self):
        return f"<UserMemory(id={self.id}, user={self.user_id}, type={self.memory_type}, key='{self.key[:30]}')>"


class MemoryAuditLog(Base):
    """
    Log de auditoria para operações de memória.

    Registra todas as operações para compliance (LGPD) e debugging.
    Nunca deletar - apenas rotacionar após período de retenção.
    """

    __tablename__ = "memory_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_id = Column(Integer, ForeignKey("user_memories.id", ondelete="SET NULL"), nullable=True, index=True)

    # ==================== OPERAÇÃO ====================
    operation = Column(String(50), nullable=False, index=True)
    # Valores: create, update, delete, decay, expire, override, admin_override

    # ==================== SNAPSHOT ====================
    old_value = Column(JSON)
    new_value = Column(JSON)
    old_confidence = Column(Float)
    new_confidence = Column(Float)

    # ==================== CONTEXTO ====================
    reason = Column(String(255))
    # Valores: user_request, decay_job, system_cleanup, admin_action, etc

    session_id = Column(String(100))

    # ==================== TEMPORALIDADE ====================
    created_at = Column(DateTime, default=utc_now, index=True)

    # ==================== RELATIONSHIPS ====================
    memory = relationship("UserMemory", back_populates="audit_logs")

    # ==================== ÍNDICES ====================
    __table_args__ = (
        Index("idx_audit_user_date", "user_id", "created_at"),
        Index("idx_audit_operation", "operation", "created_at"),
    )

    def __repr__(self):
        return f"<MemoryAuditLog(id={self.id}, op={self.operation}, memory={self.memory_id})>"


# ==================== CONSTANTES ====================

# Confiança inicial por fonte
SOURCE_CONFIDENCE = {
    MemorySourceEnum.USER_EXPLICIT: 0.9,
    MemorySourceEnum.USER_IMPLICIT: 0.7,
    MemorySourceEnum.INFERENCE: 0.5,
    MemorySourceEnum.SYSTEM: 1.0,
}

# Limites por tipo de memória (por usuário)
MEMORY_LIMITS = {
    MemoryTypeEnum.PREFERENCE: 50,
    MemoryTypeEnum.HABIT: 30,
    MemoryTypeEnum.CONSTRAINT: 20,
    MemoryTypeEnum.IDENTITY: 10,
    MemoryTypeEnum.RECURRENCE: 30,
    MemoryTypeEnum.EVENT: 100,
    MemoryTypeEnum.ACTION: 500,
    MemoryTypeEnum.DECISION: 200,
    MemoryTypeEnum.CONTEXT: 20,
    MemoryTypeEnum.INFERENCE: 50,
}

# Importância por tipo (padrão)
TYPE_IMPORTANCE = {
    MemoryTypeEnum.CONSTRAINT: ImportanceEnum.CRITICAL,
    MemoryTypeEnum.IDENTITY: ImportanceEnum.HIGH,
    MemoryTypeEnum.PREFERENCE: ImportanceEnum.MEDIUM,
    MemoryTypeEnum.HABIT: ImportanceEnum.MEDIUM,
    MemoryTypeEnum.RECURRENCE: ImportanceEnum.HIGH,
    MemoryTypeEnum.EVENT: ImportanceEnum.LOW,
    MemoryTypeEnum.ACTION: ImportanceEnum.LOW,
    MemoryTypeEnum.DECISION: ImportanceEnum.MEDIUM,
    MemoryTypeEnum.CONTEXT: ImportanceEnum.LOW,
    MemoryTypeEnum.INFERENCE: ImportanceEnum.LOW,
}

# Decay por tipo (taxa_diaria, confiança_mínima, nunca_decai)
DECAY_CONFIG = {
    MemoryTypeEnum.CONSTRAINT: (0.0, 0.5, True),  # Nunca decai
    MemoryTypeEnum.IDENTITY: (0.002, 0.3, False),  # -0.2%/dia
    MemoryTypeEnum.PREFERENCE: (0.005, 0.3, False),  # -0.5%/dia
    MemoryTypeEnum.HABIT: (0.01, 0.3, False),  # -1%/dia
    MemoryTypeEnum.RECURRENCE: (0.02, 0.2, False),  # -2%/dia
    MemoryTypeEnum.DECISION: (0.02, 0.2, False),  # -2%/dia
    MemoryTypeEnum.EVENT: (0.03, 0.1, False),  # -3%/dia
    MemoryTypeEnum.ACTION: (0.05, 0.1, False),  # -5%/dia
    MemoryTypeEnum.CONTEXT: (0.1, 0.0, False),  # -10%/dia
    MemoryTypeEnum.INFERENCE: (0.1, 0.0, False),  # -10%/dia
}

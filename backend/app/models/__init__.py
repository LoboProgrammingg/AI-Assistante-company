"""
Modelos do sistema IRIS - separados por funcionalidade.
"""

# Cache e métricas da IA
from app.models.ai_cache import AgentMetrics, ClassificationCache, ConversationMemory

# Base e utilitários
from app.models.base import Base, RecurrenceType, utc_now

# Documentos e RAG
from app.models.document import Document, DocumentCategory, DocumentEmbedding

# Finanças
from app.models.finance import Finance, FinanceCategory, FinanceType

# Integrações externas
from app.models.integration import UserIntegration

# Reuniões
from app.models.meeting import (
    Meeting,
    MeetingArtifact,
    MeetingChunk,
    MeetingSession,
    MeetingStatus,
    SessionSourceType,
    SessionStatus,
)

# Mensagens
from app.models.message import Message

# Lembretes
from app.models.reminder_model import Reminder

# Mensagens agendadas
from app.models.scheduled_message import ScheduledMessage, ScheduledMessageStatus

# Planos e assinaturas
from app.models.subscription import Plan, PlanType, Subscription, SubscriptionStatus

# Gerenciador de Tarefas
from app.models.task import Project, Task, TaskLabel, TaskPriority, TaskStatus

# Usuário e autenticação
from app.models.user import User, VerificationToken, VerificationTokenType

# Memória estruturada v3
from app.models.user_memory import (
    DECAY_CONFIG,
    MEMORY_LIMITS,
    SOURCE_CONFIDENCE,
    TYPE_IMPORTANCE,
    ImportanceEnum,
    MemoryAuditLog,
    MemoryLayerEnum,
    MemorySourceEnum,
    MemoryTypeEnum,
    UserMemory,
)

__all__ = [
    "Base",
    "RecurrenceType",
    "FinanceType",
    "User",
    "UserIntegration",
    "Message",
    "Reminder",
    "FinanceCategory",
    "Finance",
    "Meeting",
    "MeetingSession",
    "MeetingChunk",
    "MeetingArtifact",
    "MeetingStatus",
    "SessionStatus",
    "SessionSourceType",
    "ConversationMemory",
    "ScheduledMessage",
    "ScheduledMessageStatus",
    "VerificationToken",
    "VerificationTokenType",
    "Plan",
    "PlanType",
    "Subscription",
    "SubscriptionStatus",
    "Document",
    "DocumentCategory",
    "DocumentEmbedding",
    "ClassificationCache",
    "AgentMetrics",
    # Gerenciador de Tarefas
    "Task",
    "TaskStatus",
    "TaskPriority",
    "Project",
    "TaskLabel",
    # Memory v3
    "UserMemory",
    "MemoryAuditLog",
    "MemoryTypeEnum",
    "MemoryLayerEnum",
    "ImportanceEnum",
    "MemorySourceEnum",
    "SOURCE_CONFIDENCE",
    "MEMORY_LIMITS",
    "TYPE_IMPORTANCE",
    "DECAY_CONFIG",
]

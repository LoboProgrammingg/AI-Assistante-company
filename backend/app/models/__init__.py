"""
Modelos do sistema IRIS - separados por funcionalidade.
"""

# Base e utilitários
from app.models.base import Base, RecurrenceType, utc_now

# Usuário e autenticação
from app.models.user import User, VerificationToken, VerificationTokenType

# Mensagens
from app.models.message import Message

# Lembretes
from app.models.reminder_model import Reminder

# Finanças
from app.models.finance import Finance, FinanceCategory, FinanceType

# Reuniões
from app.models.meeting import Meeting

# Contatos e mensagens agendadas
from app.models.contact import Contact, ContactGroupEnum, CustomContactGroup, ScheduledMessage, ScheduledMessageStatus

# Planos e assinaturas
from app.models.subscription import Plan, PlanType, Subscription, SubscriptionStatus

# Documentos e RAG
from app.models.document import Document, DocumentCategory, DocumentEmbedding

# Cache e métricas da IA
from app.models.ai_cache import AgentMetrics, ClassificationCache, ConversationMemory

# Memória estruturada v3
from app.models.user_memory import (
    UserMemory,
    MemoryAuditLog,
    MemoryTypeEnum,
    MemoryLayerEnum,
    ImportanceEnum,
    MemorySourceEnum,
    SOURCE_CONFIDENCE,
    MEMORY_LIMITS,
    TYPE_IMPORTANCE,
    DECAY_CONFIG,
)

# Integrações externas
from app.models.integration import UserIntegration

__all__ = [
    "Base",
    "RecurrenceType",
    "FinanceType",
    "ContactGroupEnum",
    "CustomContactGroup",
    "User",
    "UserIntegration",
    "Message",
    "Reminder",
    "FinanceCategory",
    "Finance",
    "Meeting",
    "ConversationMemory",
    "Contact",
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

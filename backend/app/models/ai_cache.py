"""
Modelos de cache e métricas da IA.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, utc_now


class ConversationMemory(Base):
    __tablename__ = "conversation_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Memory content
    key = Column(String, nullable=False)
    value = Column(JSON, nullable=False)

    # Context
    context_window = Column(Integer, default=10)  # Last N messages

    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    accessed_at = Column(DateTime, default=utc_now)


class ClassificationCache(Base):
    """Cache de classificações de intenção para evitar chamadas repetidas à LLM."""

    __tablename__ = "classification_cache"

    id = Column(Integer, primary_key=True, index=True)
    message_hash = Column(String(64), unique=True, nullable=False, index=True)
    intent = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    entities = Column(JSON, default={})
    hit_count = Column(Integer, default=1)
    last_used_at = Column(DateTime, default=utc_now)
    created_at = Column(DateTime, default=utc_now)


class AgentMetrics(Base):
    """Métricas de performance dos agentes."""

    __tablename__ = "agent_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_name = Column(String(50), nullable=False)
    action_type = Column(String(50), nullable=False)
    success = Column(Boolean, default=True)
    confidence = Column(Float, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now, index=True)

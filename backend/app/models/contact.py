"""
Modelos de contatos e grupos.
"""

import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, RecurrenceType, utc_now


class ContactGroupEnum(enum.Enum):
    """Grupos padrão de contatos (mantido para compatibilidade)."""

    FAMILY = "family"
    FRIEND = "friend"
    EMPLOYEE = "employee"
    COLLEAGUE = "colleague"
    CLIENT = "client"
    OTHER = "other"


class CustomContactGroup(Base):
    """Grupos customizados de contatos criados pelo usuário."""

    __tablename__ = "custom_contact_groups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String(100), nullable=False)  # Nome do grupo (ex: "Funcionários", "Família")
    slug = Column(String(100), nullable=False)  # Slug para busca (ex: "funcionarios", "familia")
    description = Column(Text, nullable=True)
    icon = Column(String(10), nullable=True)  # Emoji para o grupo

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="contact_groups")
    contacts = relationship("Contact", back_populates="custom_group")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("custom_contact_groups.id"), nullable=True)

    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    group_name = Column(String(100), default="outros")  # Nome do grupo (flexível)
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="contacts")
    custom_group = relationship("CustomContactGroup", back_populates="contacts")
    scheduled_messages = relationship("ScheduledMessage", back_populates="contact")


class ScheduledMessageStatus(enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledMessage(Base):
    """Mensagens agendadas para envio automático a contatos."""

    __tablename__ = "scheduled_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)

    # Destinatário (pode ser contato ou grupo)
    recipient_phone = Column(String, nullable=True)  # Telefone direto (se não for contato)
    recipient_name = Column(String, nullable=True)  # Nome do destinatário
    group_name = Column(String(100), nullable=True)  # Se for para um grupo inteiro

    # Mensagem
    message = Column(Text, nullable=False)

    # Agendamento
    scheduled_time = Column(DateTime, nullable=False)

    # Status
    status = Column(Enum(ScheduledMessageStatus), default=ScheduledMessageStatus.PENDING)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Recorrência (opcional)
    recurrence_type = Column(Enum(RecurrenceType), default=RecurrenceType.ONCE)

    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="scheduled_messages")
    contact = relationship("Contact", back_populates="scheduled_messages")

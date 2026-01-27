"""
Modelo de mensagens agendadas.
"""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, utc_now


class ScheduledMessageStatus(enum.Enum):
    """Status das mensagens agendadas."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledMessage(Base):
    """Modelo para mensagens agendadas."""

    __tablename__ = "scheduled_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    recipient_phone = Column(String(20), nullable=True)
    recipient_name = Column(String(100), nullable=True)
    group_name = Column(String(100), nullable=True)

    message = Column(Text, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)

    status = Column(
        Enum(ScheduledMessageStatus),
        default=ScheduledMessageStatus.PENDING,
        nullable=False,
    )

    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="scheduled_messages")

    def __repr__(self):
        return (
            f"<ScheduledMessage(id={self.id}, to={self.recipient_name or self.group_name}, status={self.status.value})>"
        )

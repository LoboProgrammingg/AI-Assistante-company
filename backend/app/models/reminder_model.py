"""
Modelo de lembretes.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, RecurrenceType, utc_now


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Reminder details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Timing
    scheduled_time = Column(DateTime, nullable=False)
    remind_before_minutes = Column(Integer, default=0)
    actual_reminder_time = Column(DateTime, nullable=False)

    # Recurrence
    recurrence_type = Column(Enum(RecurrenceType), default=RecurrenceType.ONCE)
    recurrence_config = Column(JSON, nullable=True)  # Para custom patterns

    # Status
    is_active = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="reminders")

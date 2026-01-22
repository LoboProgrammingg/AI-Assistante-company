"""
Modelo de reuniões.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, utc_now


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Meeting details
    title = Column(String, nullable=True)
    date = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    # Audio
    audio_url = Column(String, nullable=True)
    transcription = Column(Text, nullable=True)

    # AI Analysis
    summary = Column(Text, nullable=True)
    key_topics = Column(JSON, default=[])
    action_items = Column(JSON, default=[])
    participants = Column(JSON, default=[])
    decisions = Column(JSON, default=[])

    # Additional metadata
    sentiment = Column(String, nullable=True)
    keywords = Column(JSON, default=[])

    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="meetings")

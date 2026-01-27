"""
Modelo de mensagens do chat.
"""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, utc_now


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Message content
    message_type = Column(String)  # text, audio, image
    content = Column(Text, nullable=True)
    audio_url = Column(String, nullable=True)
    audio_transcription = Column(Text, nullable=True)

    # Message direction
    direction = Column(String)  # incoming, outgoing

    # WhatsApp specific
    wa_message_id = Column(String, unique=True, index=True)
    wa_status = Column(String, nullable=True)

    # AI Processing
    intent = Column(String, nullable=True)
    entities = Column(JSON, nullable=True)
    ai_response = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=utc_now)
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="messages")

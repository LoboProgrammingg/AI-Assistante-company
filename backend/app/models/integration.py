"""
Modelos de integrações externas (Google Calendar, etc).
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, utc_now


class UserIntegration(Base):
    """Integrações OAuth de terceiros (Google Calendar, etc)."""

    __tablename__ = "user_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # google_calendar, outlook, etc

    # OAuth tokens (criptografados em produção)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)

    # Informações da conta conectada
    account_email = Column(String(255), nullable=True)
    account_name = Column(String(255), nullable=True)

    # Scopes autorizados
    scopes = Column(JSON, default=[])

    # Status
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationship
    user = relationship("User", backref="integrations")

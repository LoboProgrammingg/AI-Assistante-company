"""
Base model e utilitários compartilhados.
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
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


def utc_now():
    """Retorna datetime atual em UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


class RecurrenceType(enum.Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKDAYS = "weekdays"  # Segunda a Sexta
    WEEKENDS = "weekends"  # Sábado e Domingo
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"

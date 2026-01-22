"""
Modelos de finanças.
"""

import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, RecurrenceType, utc_now


class FinanceType(enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class FinanceCategory(Base):
    __tablename__ = "finance_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(Enum(FinanceType), nullable=False)
    icon = Column(String, nullable=True)
    color = Column(String, nullable=True)

    # Relationships
    finances = relationship("Finance", back_populates="category")


class Finance(Base):
    __tablename__ = "finances"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("finance_categories.id"), nullable=True)

    # Finance details
    type = Column(Enum(FinanceType), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)

    # Timing
    transaction_date = Column(DateTime, nullable=False)

    # Recurrence (for recurring expenses/income)
    is_recurring = Column(Boolean, default=False)
    recurrence_type = Column(Enum(RecurrenceType), nullable=True)

    # Tags for better organization
    tags = Column(JSON, default=[])

    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="finances")
    category = relationship("FinanceCategory", back_populates="finances")

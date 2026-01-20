from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class FinanceTypeEnum(str, Enum):
    """Tipos de transação financeira."""

    INCOME = "income"
    EXPENSE = "expense"


class FinanceCategoryBase(BaseModel):
    """Schema base para categoria financeira."""

    name: str = Field(..., max_length=50)
    type: FinanceTypeEnum
    icon: Optional[str] = Field(None, max_length=10)
    color: Optional[str] = Field(None, max_length=7)


class FinanceCategoryResponse(FinanceCategoryBase):
    """Schema de resposta de categoria."""

    id: int

    class Config:
        from_attributes = True


class FinanceBase(BaseModel):
    """Schema base para transação financeira."""

    type: FinanceTypeEnum
    amount: float = Field(..., gt=0)
    description: Optional[str] = Field(None, max_length=500)
    transaction_date: date
    is_recurring: bool = False
    tags: List[str] = Field(default_factory=list)

    @field_validator("amount")
    @classmethod
    def round_amount(cls, v: float) -> float:
        return round(v, 2)


class FinanceCreate(FinanceBase):
    """Schema para criação de transação."""

    category_id: Optional[int] = None


class FinanceUpdate(BaseModel):
    """Schema para atualização de transação."""

    type: Optional[FinanceTypeEnum] = None
    amount: Optional[float] = Field(None, gt=0)
    description: Optional[str] = Field(None, max_length=500)
    category_id: Optional[int] = None
    transaction_date: Optional[date] = None
    tags: Optional[List[str]] = None

    @field_validator("amount")
    @classmethod
    def round_amount(cls, v: Optional[float]) -> Optional[float]:
        return round(v, 2) if v is not None else None


class FinanceResponse(FinanceBase):
    """Schema de resposta de transação."""

    id: int
    user_id: int
    category: Optional[FinanceCategoryResponse] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FinanceListResponse(BaseModel):
    """Schema para lista paginada de transações."""

    items: List[FinanceResponse]
    total: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool


class FinanceSummary(BaseModel):
    """Resumo financeiro de um período."""

    period: dict
    summary: dict
    by_category: List[dict]
    comparison: Optional[dict] = None


class CategorySummary(BaseModel):
    """Resumo por categoria."""

    category: str
    total: float
    percentage: float
    transactions_count: int


class FinanceTrend(BaseModel):
    """Tendência financeira."""

    monthly_data: List[dict]
    average_monthly_expense: float
    highest_expense_month: str
    category_trends: List[dict]


class FinanceFromAI(BaseModel):
    """Schema para criação de transação via IA."""

    type: str
    amount: float
    description: Optional[str] = None
    category: str
    transaction_date: str
    is_recurring: bool = False
    tags: List[str] = Field(default_factory=list)

    @field_validator("transaction_date")
    @classmethod
    def parse_date(cls, v: str) -> str:
        date.fromisoformat(v)
        return v

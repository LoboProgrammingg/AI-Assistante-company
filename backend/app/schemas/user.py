from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class UserBase(BaseModel):
    """Schema base para usuário."""
    name: Optional[str] = Field(None, max_length=100)
    timezone: str = Field(default="America/Sao_Paulo", max_length=50)
    language: str = Field(default="pt-BR", max_length=10)
    preferences: Dict[str, Any] = Field(default_factory=dict)


class UserCreate(UserBase):
    """Schema para criação de usuário."""
    phone_number: str = Field(..., max_length=20)


class UserUpdate(BaseModel):
    """Schema para atualização de usuário."""
    name: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=50)
    language: Optional[str] = Field(None, max_length=10)
    preferences: Optional[Dict[str, Any]] = None


class UserResponse(UserBase):
    """Schema de resposta do usuário."""
    id: int
    phone_number: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    last_interaction: datetime

    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """Estatísticas do usuário."""
    total_reminders: int = 0
    active_reminders: int = 0
    completed_reminders: int = 0
    total_transactions: int = 0
    total_income: float = 0.0
    total_expenses: float = 0.0
    total_meetings: int = 0
    total_messages: int = 0
    member_since: Optional[datetime] = None
    last_activity: Optional[datetime] = None

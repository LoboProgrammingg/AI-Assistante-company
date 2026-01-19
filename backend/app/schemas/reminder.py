from pydantic import BaseModel, Field, field_validator, field_serializer
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum


class RecurrenceTypeEnum(str, Enum):
    """Tipos de recorrência disponíveis."""
    ONCE = "once"
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKENDS = "weekends"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class ReminderBase(BaseModel):
    """Schema base para lembrete."""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    scheduled_time: datetime
    remind_before_minutes: int = Field(default=0, ge=0, le=10080)
    recurrence_type: RecurrenceTypeEnum = Field(default=RecurrenceTypeEnum.ONCE)
    recurrence_config: Optional[Dict[str, Any]] = None


class ReminderCreate(ReminderBase):
    """Schema para criação de lembrete."""
    pass


class ReminderUpdate(BaseModel):
    """Schema para atualização de lembrete."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    scheduled_time: Optional[datetime] = None
    remind_before_minutes: Optional[int] = Field(None, ge=0, le=10080)
    recurrence_type: Optional[RecurrenceTypeEnum] = None
    recurrence_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ReminderResponse(ReminderBase):
    """Schema de resposta do lembrete."""
    id: int
    user_id: int
    actual_reminder_time: datetime
    is_active: bool
    is_completed: bool
    notified: bool
    notified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_serializer('scheduled_time', 'actual_reminder_time', 'created_at', 'updated_at', 'notified_at')
    def serialize_datetime(self, v: Optional[datetime]) -> Optional[str]:
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()


class ReminderListResponse(BaseModel):
    """Schema para lista paginada de lembretes."""
    items: List[ReminderResponse]
    total: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool


class ReminderFromAI(BaseModel):
    """Schema para criação de lembrete via IA."""
    title: str
    description: Optional[str] = None
    scheduled_time: str
    remind_before_minutes: int = 0
    recurrence_type: str = "once"

    @field_validator('scheduled_time')
    @classmethod
    def parse_datetime(cls, v: str) -> str:
        datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

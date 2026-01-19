# 📊 Modelos e Schemas

## Visão Geral

O sistema utiliza:
- **SQLAlchemy** para models (ORM)
- **Pydantic** para schemas (validação/serialização)

---

## Diagrama ER (Entity-Relationship)

```
┌─────────────────────────────────────────────────────────────────────┐
│                              USERS                                   │
├─────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                             │
│ phone_number (UNIQUE)                                               │
│ session_id (UNIQUE)                                                 │
│ name                                                                 │
│ timezone                                                             │
│ language                                                             │
│ preferences (JSON)                                                   │
│ created_at, updated_at, last_interaction                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┬─────────────────┐
         │                 │                 │                 │
         ▼                 ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐
│    MESSAGES     │ │  REMINDERS  │ │  FINANCES   │ │    MEETINGS     │
├─────────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────────┤
│ id (PK)         │ │ id (PK)     │ │ id (PK)     │ │ id (PK)         │
│ user_id (FK)    │ │ user_id (FK)│ │ user_id (FK)│ │ user_id (FK)    │
│ message_type    │ │ title       │ │ type        │ │ title           │
│ content         │ │ description │ │ amount      │ │ transcription   │
│ audio_url       │ │ scheduled_  │ │ category_id │ │ summary         │
│ transcription   │ │   time      │ │ description │ │ key_topics      │
│ direction       │ │ remind_     │ │ transaction_│ │ action_items    │
│ wa_message_id   │ │   before    │ │   date      │ │ participants    │
│ intent          │ │ recurrence_ │ │ is_recurring│ │ decisions       │
│ entities        │ │   type      │ │ tags        │ │ sentiment       │
│ ai_response     │ │ is_active   │ │ created_at  │ │ keywords        │
│ created_at      │ │ notified    │ └─────┬───────┘ │ audio_url       │
└─────────────────┘ └─────────────┘       │         │ created_at      │
                                          │         └─────────────────┘
                                          ▼
                                   ┌─────────────────┐
                                   │FINANCE_CATEGORIES│
                                   ├─────────────────┤
                                   │ id (PK)         │
                                   │ name (UNIQUE)   │
                                   │ type            │
                                   │ icon            │
                                   │ color           │
                                   └─────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      CONVERSATION_MEMORY                             │
├─────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                             │
│ user_id (FK)                                                        │
│ key                                                                  │
│ value (JSON)                                                         │
│ context_window                                                       │
│ created_at, updated_at, accessed_at                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## SQLAlchemy Models

### User Model

```python
# app/models/user.py

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    timezone = Column(String(50), default="America/Sao_Paulo")
    language = Column(String(10), default="pt-BR")
    preferences = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_interaction = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    finances = relationship("Finance", back_populates="user", cascade="all, delete-orphan")
    meetings = relationship("Meeting", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("ConversationMemory", back_populates="user", cascade="all, delete-orphan")
```

### Message Model

```python
# app/models/message.py

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    message_type = Column(String(20))  # text, audio, image
    content = Column(Text, nullable=True)
    audio_url = Column(String(500), nullable=True)
    audio_transcription = Column(Text, nullable=True)
    
    direction = Column(String(10))  # incoming, outgoing
    
    wa_message_id = Column(String(100), unique=True, index=True)
    wa_status = Column(String(20), nullable=True)  # sent, delivered, read, failed
    
    intent = Column(String(50), nullable=True)
    entities = Column(JSON, nullable=True)
    ai_response = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="messages")
```

### Reminder Model

```python
# app/models/reminder.py

import enum

class RecurrenceType(enum.Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKENDS = "weekends"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class Reminder(Base):
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    scheduled_time = Column(DateTime, nullable=False, index=True)
    remind_before_minutes = Column(Integer, default=0)
    actual_reminder_time = Column(DateTime, nullable=False, index=True)
    
    recurrence_type = Column(Enum(RecurrenceType), default=RecurrenceType.ONCE)
    recurrence_config = Column(JSON, nullable=True)
    
    is_active = Column(Boolean, default=True, index=True)
    is_completed = Column(Boolean, default=False)
    notified = Column(Boolean, default=False, index=True)
    notified_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="reminders")
```

### Finance Models

```python
# app/models/finance.py

class FinanceType(enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class FinanceCategory(Base):
    __tablename__ = "finance_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    type = Column(Enum(FinanceType), nullable=False)
    icon = Column(String(10), nullable=True)
    color = Column(String(7), nullable=True)  # #RRGGBB
    
    finances = relationship("Finance", back_populates="category")


class Finance(Base):
    __tablename__ = "finances"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("finance_categories.id"), nullable=True)
    
    type = Column(Enum(FinanceType), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    
    transaction_date = Column(Date, nullable=False, index=True)
    
    is_recurring = Column(Boolean, default=False)
    recurrence_type = Column(Enum(RecurrenceType), nullable=True)
    
    tags = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="finances")
    category = relationship("FinanceCategory", back_populates="finances")
```

### Meeting Model

```python
# app/models/meeting.py

class Meeting(Base):
    __tablename__ = "meetings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    title = Column(String(200), nullable=True)
    date = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    
    audio_url = Column(String(500), nullable=True)
    transcription = Column(Text, nullable=True)
    
    summary = Column(Text, nullable=True)
    key_topics = Column(JSON, default=list)
    action_items = Column(JSON, default=list)
    participants = Column(JSON, default=list)
    decisions = Column(JSON, default=list)
    
    sentiment = Column(String(20), nullable=True)  # positivo, neutro, negativo
    keywords = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="meetings")
```

### Conversation Memory Model

```python
# app/models/memory.py

class ConversationMemory(Base):
    __tablename__ = "conversation_memory"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    key = Column(String(100), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    
    context_window = Column(Integer, default=10)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    accessed_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="memories")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'key', name='uq_user_memory_key'),
    )
```

---

## Pydantic Schemas

### User Schemas

```python
# app/schemas/user.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class UserBase(BaseModel):
    name: Optional[str] = None
    timezone: str = "America/Sao_Paulo"
    language: str = "pt-BR"
    preferences: Dict[str, Any] = Field(default_factory=dict)


class UserCreate(UserBase):
    phone_number: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class UserResponse(UserBase):
    id: int
    phone_number: str
    session_id: str
    created_at: datetime
    last_interaction: datetime
    
    class Config:
        from_attributes = True


class UserStats(BaseModel):
    total_reminders: int
    active_reminders: int
    total_transactions: int
    total_meetings: int
    member_since: datetime
    last_activity: datetime
```

### Reminder Schemas

```python
# app/schemas/reminder.py

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class RecurrenceTypeEnum(str, Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKENDS = "weekends"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class ReminderBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    scheduled_time: datetime
    remind_before_minutes: int = Field(default=0, ge=0, le=10080)  # max 1 semana
    recurrence_type: RecurrenceTypeEnum = RecurrenceTypeEnum.ONCE
    recurrence_config: Optional[Dict[str, Any]] = None


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    remind_before_minutes: Optional[int] = Field(None, ge=0, le=10080)
    recurrence_type: Optional[RecurrenceTypeEnum] = None
    is_active: Optional[bool] = None


class ReminderResponse(ReminderBase):
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


class ReminderList(BaseModel):
    items: list[ReminderResponse]
    total: int
    page: int
    pages: int
    has_next: bool
```

### Finance Schemas

```python
# app/schemas/finance.py

from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import Optional, List
from enum import Enum
from decimal import Decimal


class FinanceTypeEnum(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class FinanceCategoryResponse(BaseModel):
    id: int
    name: str
    type: FinanceTypeEnum
    icon: Optional[str] = None
    color: Optional[str] = None
    
    class Config:
        from_attributes = True


class FinanceBase(BaseModel):
    type: FinanceTypeEnum
    amount: float = Field(..., gt=0)
    description: Optional[str] = None
    transaction_date: date
    is_recurring: bool = False
    tags: List[str] = Field(default_factory=list)
    
    @validator('amount')
    def round_amount(cls, v):
        return round(v, 2)


class FinanceCreate(FinanceBase):
    category_id: Optional[int] = None


class FinanceUpdate(BaseModel):
    type: Optional[FinanceTypeEnum] = None
    amount: Optional[float] = Field(None, gt=0)
    description: Optional[str] = None
    category_id: Optional[int] = None
    transaction_date: Optional[date] = None
    tags: Optional[List[str]] = None


class FinanceResponse(FinanceBase):
    id: int
    user_id: int
    category: Optional[FinanceCategoryResponse] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class FinanceSummary(BaseModel):
    period: dict
    summary: dict
    by_category: List[dict]
    comparison: Optional[dict] = None


class FinanceTrend(BaseModel):
    monthly_data: List[dict]
    average_monthly_expense: float
    highest_expense_month: str
    category_trends: List[dict]
```

### Meeting Schemas

```python
# app/schemas/meeting.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any


class ActionItem(BaseModel):
    task: str
    responsible: Optional[str] = None
    deadline: Optional[str] = None
    priority: str = "medium"
    status: str = "pending"


class Participant(BaseModel):
    name: str
    role: Optional[str] = None


class Decision(BaseModel):
    decision: str
    context: Optional[str] = None


class KeyTopic(BaseModel):
    topic: str
    summary: Optional[str] = None
    discussed_by: List[str] = Field(default_factory=list)


class MeetingBase(BaseModel):
    title: Optional[str] = None
    date: Optional[datetime] = None
    duration_minutes: Optional[int] = None


class MeetingCreate(MeetingBase):
    summary: Optional[str] = None
    key_topics: List[str] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    participants: List[str] = Field(default_factory=list)


class MeetingResponse(MeetingBase):
    id: int
    user_id: int
    audio_url: Optional[str] = None
    transcription: Optional[str] = None
    summary: Optional[str] = None
    key_topics: List[KeyTopic] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    participants: List[Participant] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    sentiment: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    created_at: datetime
    
    class Config:
        from_attributes = True


class MeetingListItem(BaseModel):
    id: int
    title: Optional[str] = None
    date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    summary: Optional[str] = None
    key_topics: List[str] = Field(default_factory=list)
    action_items_count: int
    participants_count: int
    sentiment: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class MeetingAnalysisRequest(BaseModel):
    transcription: str


class MeetingSearchResult(BaseModel):
    meeting_id: int
    title: Optional[str] = None
    highlights: List[str]
    relevance_score: float
```

---

## Índices do Banco de Dados

```sql
-- Índices de performance
CREATE INDEX idx_messages_user_created ON messages(user_id, created_at DESC);
CREATE INDEX idx_reminders_user_active ON reminders(user_id, is_active, actual_reminder_time);
CREATE INDEX idx_reminders_notification ON reminders(notified, actual_reminder_time) WHERE is_active = true;
CREATE INDEX idx_finances_user_date ON finances(user_id, transaction_date DESC);
CREATE INDEX idx_finances_user_type ON finances(user_id, type);
CREATE INDEX idx_meetings_user_date ON meetings(user_id, date DESC);
CREATE INDEX idx_memory_user_key ON conversation_memory(user_id, key);
```

---

## Categorias Padrão (Seed)

```python
DEFAULT_CATEGORIES = [
    # Expenses
    {"name": "Alimentação", "type": "expense", "icon": "🍔", "color": "#e74c3c"},
    {"name": "Transporte", "type": "expense", "icon": "🚗", "color": "#3498db"},
    {"name": "Moradia", "type": "expense", "icon": "🏠", "color": "#9b59b6"},
    {"name": "Saúde", "type": "expense", "icon": "💊", "color": "#1abc9c"},
    {"name": "Lazer", "type": "expense", "icon": "🎮", "color": "#f39c12"},
    {"name": "Educação", "type": "expense", "icon": "📚", "color": "#2ecc71"},
    {"name": "Vestuário", "type": "expense", "icon": "👕", "color": "#e91e63"},
    {"name": "Serviços", "type": "expense", "icon": "📱", "color": "#00bcd4"},
    {"name": "Outros", "type": "expense", "icon": "📦", "color": "#95a5a6"},
    
    # Income
    {"name": "Salário", "type": "income", "icon": "💰", "color": "#27ae60"},
    {"name": "Freelance", "type": "income", "icon": "💻", "color": "#8e44ad"},
    {"name": "Investimentos", "type": "income", "icon": "📈", "color": "#16a085"},
    {"name": "Outros", "type": "income", "icon": "💵", "color": "#7f8c8d"},
]
```

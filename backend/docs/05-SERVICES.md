# ⚙️ Camada de Services

## Visão Geral

Os Services contêm a lógica de negócio da aplicação, separando-a dos endpoints e modelos.

---

## Estrutura

```
app/services/
├── __init__.py
├── whatsapp_service.py    # ✅ Implementado
├── ai_service.py          # 📝 Pendente
├── reminder_service.py    # 📝 Pendente
├── finance_service.py     # 📝 Pendente
├── meeting_service.py     # 📝 Pendente
└── memory_service.py      # 📝 Pendente
```

---

## 1. Reminder Service

```python
# app/services/reminder_service.py

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
import pytz

from app.models import Reminder, User, RecurrenceType
from app.schemas.reminder import ReminderCreate, ReminderUpdate


class ReminderService:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, user_id: int, data: ReminderCreate) -> Reminder:
        """Cria novo lembrete."""
        actual_time = data.scheduled_time - timedelta(
            minutes=data.remind_before_minutes
        )
        
        reminder = Reminder(
            user_id=user_id,
            title=data.title,
            description=data.description,
            scheduled_time=data.scheduled_time,
            remind_before_minutes=data.remind_before_minutes,
            actual_reminder_time=actual_time,
            recurrence_type=RecurrenceType(data.recurrence_type),
            recurrence_config=data.recurrence_config,
            is_active=True
        )
        
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        return reminder
    
    async def create_from_entities(
        self, 
        user_id: int, 
        entities: dict
    ) -> Reminder:
        """Cria lembrete a partir de entidades extraídas pela IA."""
        data = ReminderCreate(
            title=entities.get("title", "Lembrete"),
            description=entities.get("description"),
            scheduled_time=datetime.fromisoformat(entities["scheduled_time"]),
            remind_before_minutes=entities.get("remind_before_minutes", 0),
            recurrence_type=entities.get("recurrence_type", "once")
        )
        return self.create(user_id, data)
    
    def get_by_id(self, reminder_id: int, user_id: int) -> Optional[Reminder]:
        """Busca lembrete por ID."""
        return self.db.query(Reminder).filter(
            and_(Reminder.id == reminder_id, Reminder.user_id == user_id)
        ).first()
    
    def list_by_user(
        self,
        user_id: int,
        status: str = "active",
        limit: int = 20,
        offset: int = 0
    ) -> List[Reminder]:
        """Lista lembretes do usuário."""
        query = self.db.query(Reminder).filter(Reminder.user_id == user_id)
        
        if status == "active":
            query = query.filter(Reminder.is_active == True)
        elif status == "completed":
            query = query.filter(Reminder.is_completed == True)
        
        return query.order_by(Reminder.scheduled_time).offset(offset).limit(limit).all()
    
    def update(
        self, 
        reminder_id: int, 
        user_id: int, 
        data: ReminderUpdate
    ) -> Optional[Reminder]:
        """Atualiza lembrete."""
        reminder = self.get_by_id(reminder_id, user_id)
        if not reminder:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reminder, field, value)
        
        if data.scheduled_time or data.remind_before_minutes is not None:
            reminder.actual_reminder_time = reminder.scheduled_time - timedelta(
                minutes=reminder.remind_before_minutes
            )
        
        self.db.commit()
        self.db.refresh(reminder)
        return reminder
    
    def delete(self, reminder_id: int, user_id: int) -> bool:
        """Remove lembrete (soft delete)."""
        reminder = self.get_by_id(reminder_id, user_id)
        if not reminder:
            return False
        
        reminder.is_active = False
        self.db.commit()
        return True
    
    def complete(self, reminder_id: int, user_id: int) -> Optional[Reminder]:
        """Marca lembrete como concluído."""
        reminder = self.get_by_id(reminder_id, user_id)
        if not reminder:
            return None
        
        reminder.is_completed = True
        reminder.is_active = False
        self.db.commit()
        self.db.refresh(reminder)
        return reminder
    
    def get_upcoming(self, user_id: int, hours: int = 24) -> List[Reminder]:
        """Retorna lembretes das próximas N horas."""
        now = datetime.utcnow()
        end = now + timedelta(hours=hours)
        
        return self.db.query(Reminder).filter(
            and_(
                Reminder.user_id == user_id,
                Reminder.is_active == True,
                Reminder.actual_reminder_time >= now,
                Reminder.actual_reminder_time <= end
            )
        ).order_by(Reminder.actual_reminder_time).all()
```

---

## 2. Finance Service

```python
# app/services/finance_service.py

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, extract
from calendar import monthrange

from app.models import Finance, FinanceCategory, FinanceType
from app.schemas.finance import FinanceCreate, FinanceUpdate


class FinanceService:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, user_id: int, data: FinanceCreate) -> Finance:
        """Registra nova transação."""
        finance = Finance(
            user_id=user_id,
            type=FinanceType(data.type),
            amount=data.amount,
            description=data.description,
            category_id=data.category_id,
            transaction_date=data.transaction_date,
            is_recurring=data.is_recurring,
            tags=data.tags
        )
        
        self.db.add(finance)
        self.db.commit()
        self.db.refresh(finance)
        return finance
    
    async def create_from_entities(
        self, 
        user_id: int, 
        entities: dict
    ) -> Finance:
        """Cria transação a partir de entidades extraídas."""
        category = self._get_or_create_category(
            entities.get("category", "Outros"),
            entities.get("type", "expense")
        )
        
        data = FinanceCreate(
            type=entities.get("type", "expense"),
            amount=float(entities.get("amount", 0)),
            description=entities.get("description"),
            category_id=category.id if category else None,
            transaction_date=date.fromisoformat(
                entities.get("transaction_date", date.today().isoformat())
            ),
            tags=entities.get("tags", [])
        )
        return self.create(user_id, data)
    
    def _get_or_create_category(
        self, 
        name: str, 
        type: str
    ) -> Optional[FinanceCategory]:
        """Busca ou cria categoria."""
        category = self.db.query(FinanceCategory).filter(
            FinanceCategory.name == name
        ).first()
        
        if not category:
            category = FinanceCategory(
                name=name,
                type=FinanceType(type)
            )
            self.db.add(category)
            self.db.commit()
            self.db.refresh(category)
        
        return category
    
    def get_summary(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Retorna resumo financeiro do período."""
        
        # Totais
        income = self.db.query(func.sum(Finance.amount)).filter(
            and_(
                Finance.user_id == user_id,
                Finance.type == FinanceType.INCOME,
                Finance.transaction_date >= start_date,
                Finance.transaction_date <= end_date
            )
        ).scalar() or 0
        
        expenses = self.db.query(func.sum(Finance.amount)).filter(
            and_(
                Finance.user_id == user_id,
                Finance.type == FinanceType.EXPENSE,
                Finance.transaction_date >= start_date,
                Finance.transaction_date <= end_date
            )
        ).scalar() or 0
        
        # Por categoria
        by_category = self.db.query(
            FinanceCategory.name,
            func.sum(Finance.amount).label('total'),
            func.count(Finance.id).label('count')
        ).join(Finance).filter(
            and_(
                Finance.user_id == user_id,
                Finance.type == FinanceType.EXPENSE,
                Finance.transaction_date >= start_date,
                Finance.transaction_date <= end_date
            )
        ).group_by(FinanceCategory.name).all()
        
        return {
            "total_income": float(income),
            "total_expenses": float(expenses),
            "balance": float(income - expenses),
            "by_category": [
                {
                    "category": cat.name,
                    "total": float(cat.total),
                    "percentage": (float(cat.total) / expenses * 100) if expenses > 0 else 0,
                    "count": cat.count
                }
                for cat in by_category
            ]
        }
    
    def list_transactions(
        self,
        user_id: int,
        type: Optional[str] = None,
        category_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Finance]:
        """Lista transações com filtros."""
        query = self.db.query(Finance).filter(Finance.user_id == user_id)
        
        if type:
            query = query.filter(Finance.type == FinanceType(type))
        if category_id:
            query = query.filter(Finance.category_id == category_id)
        if start_date:
            query = query.filter(Finance.transaction_date >= start_date)
        if end_date:
            query = query.filter(Finance.transaction_date <= end_date)
        
        return query.order_by(Finance.transaction_date.desc()).offset(offset).limit(limit).all()
    
    def get_monthly_trend(
        self, 
        user_id: int, 
        months: int = 6
    ) -> List[Dict[str, Any]]:
        """Retorna tendência mensal de gastos."""
        result = []
        today = date.today()
        
        for i in range(months):
            year = today.year
            month = today.month - i
            
            if month <= 0:
                month += 12
                year -= 1
            
            start = date(year, month, 1)
            _, last_day = monthrange(year, month)
            end = date(year, month, last_day)
            
            summary = self.get_summary(user_id, start, end)
            result.append({
                "month": start.strftime("%Y-%m"),
                "income": summary["total_income"],
                "expenses": summary["total_expenses"]
            })
        
        return list(reversed(result))
```

---

## 3. Meeting Service

```python
# app/services/meeting_service.py

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import Meeting
from app.schemas.meeting import MeetingCreate


class MeetingService:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, user_id: int, data: MeetingCreate) -> Meeting:
        """Cria nova reunião."""
        meeting = Meeting(
            user_id=user_id,
            title=data.title,
            date=data.date,
            summary=data.summary,
            key_topics=[{"topic": t} for t in data.key_topics],
            action_items=[item.model_dump() for item in data.action_items],
            participants=[{"name": p} for p in data.participants]
        )
        
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
        return meeting
    
    async def create_from_entities(
        self,
        user_id: int,
        entities: dict,
        audio_url: Optional[str] = None,
        transcription: Optional[str] = None
    ) -> Meeting:
        """Cria reunião a partir de análise da IA."""
        meeting = Meeting(
            user_id=user_id,
            title=entities.get("title"),
            date=datetime.now(),
            duration_minutes=entities.get("duration_estimate"),
            audio_url=audio_url,
            transcription=transcription,
            summary=entities.get("summary"),
            key_topics=entities.get("key_topics", []),
            action_items=entities.get("action_items", []),
            participants=entities.get("participants", []),
            decisions=entities.get("decisions", []),
            sentiment=entities.get("sentiment"),
            keywords=entities.get("keywords", [])
        )
        
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
        return meeting
    
    def get_by_id(self, meeting_id: int, user_id: int) -> Optional[Meeting]:
        """Busca reunião por ID."""
        return self.db.query(Meeting).filter(
            Meeting.id == meeting_id,
            Meeting.user_id == user_id
        ).first()
    
    def list_by_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Meeting]:
        """Lista reuniões do usuário."""
        return self.db.query(Meeting).filter(
            Meeting.user_id == user_id
        ).order_by(Meeting.created_at.desc()).offset(offset).limit(limit).all()
    
    def search(
        self, 
        user_id: int, 
        query: str
    ) -> List[Dict[str, Any]]:
        """Busca em reuniões por palavra-chave."""
        meetings = self.db.query(Meeting).filter(
            Meeting.user_id == user_id,
            or_(
                Meeting.title.ilike(f"%{query}%"),
                Meeting.summary.ilike(f"%{query}%"),
                Meeting.transcription.ilike(f"%{query}%")
            )
        ).all()
        
        results = []
        for m in meetings:
            highlights = []
            if query.lower() in (m.title or "").lower():
                highlights.append(m.title)
            if query.lower() in (m.summary or "").lower():
                idx = m.summary.lower().find(query.lower())
                start = max(0, idx - 50)
                end = min(len(m.summary), idx + len(query) + 50)
                highlights.append(f"...{m.summary[start:end]}...")
            
            results.append({
                "meeting_id": m.id,
                "title": m.title,
                "highlights": highlights,
                "relevance_score": 0.9 if m.title and query.lower() in m.title.lower() else 0.7
            })
        
        return sorted(results, key=lambda x: x["relevance_score"], reverse=True)
    
    def update_action_item_status(
        self,
        meeting_id: int,
        user_id: int,
        item_index: int,
        status: str
    ) -> Optional[Meeting]:
        """Atualiza status de um action item."""
        meeting = self.get_by_id(meeting_id, user_id)
        if not meeting or item_index >= len(meeting.action_items):
            return None
        
        meeting.action_items[item_index]["status"] = status
        self.db.commit()
        self.db.refresh(meeting)
        return meeting
```

---

## 4. Memory Service

```python
# app/services/memory_service.py

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.models import ConversationMemory, Message


class MemoryService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_memory(self, user_id: int, key: str) -> Optional[Dict[str, Any]]:
        """Recupera uma memória específica."""
        memory = self.db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id,
            ConversationMemory.key == key
        ).first()
        
        if memory:
            memory.accessed_at = datetime.utcnow()
            self.db.commit()
            return memory.value
        return None
    
    def set_memory(
        self, 
        user_id: int, 
        key: str, 
        value: Dict[str, Any]
    ) -> ConversationMemory:
        """Define ou atualiza uma memória."""
        memory = self.db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id,
            ConversationMemory.key == key
        ).first()
        
        if memory:
            memory.value = value
            memory.updated_at = datetime.utcnow()
        else:
            memory = ConversationMemory(
                user_id=user_id,
                key=key,
                value=value
            )
            self.db.add(memory)
        
        self.db.commit()
        self.db.refresh(memory)
        return memory
    
    def get_conversation_context(
        self, 
        user_id: int, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Recupera últimas mensagens para contexto."""
        messages = self.db.query(Message).filter(
            Message.user_id == user_id
        ).order_by(Message.created_at.desc()).limit(limit).all()
        
        return [
            {
                "role": "user" if m.direction == "incoming" else "assistant",
                "content": m.content or m.audio_transcription,
                "timestamp": m.created_at.isoformat()
            }
            for m in reversed(messages)
        ]
    
    def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """Recupera preferências aprendidas do usuário."""
        return self.get_memory(user_id, "preferences") or {}
    
    def update_user_preferences(
        self, 
        user_id: int, 
        updates: Dict[str, Any]
    ) -> None:
        """Atualiza preferências do usuário."""
        prefs = self.get_user_preferences(user_id)
        prefs.update(updates)
        self.set_memory(user_id, "preferences", prefs)
    
    def get_learned_facts(self, user_id: int) -> Dict[str, Any]:
        """Recupera fatos aprendidos sobre o usuário."""
        return self.get_memory(user_id, "learned_facts") or {}
    
    def add_learned_fact(
        self, 
        user_id: int, 
        key: str, 
        value: Any
    ) -> None:
        """Adiciona novo fato aprendido."""
        facts = self.get_learned_facts(user_id)
        facts[key] = value
        self.set_memory(user_id, "learned_facts", facts)
```

---

## 5. AI Service (Orquestrador)

```python
# app/services/ai_service.py

from typing import Dict, Any
from sqlalchemy.orm import Session

from app.ai.graph import WhatsAppAIAgent
from app.services.memory_service import MemoryService
from app.services.reminder_service import ReminderService
from app.services.finance_service import FinanceService
from app.services.meeting_service import MeetingService


class AIService:
    def __init__(
        self, 
        db: Session, 
        ai_agent: WhatsAppAIAgent
    ):
        self.db = db
        self.ai_agent = ai_agent
        self.memory_service = MemoryService(db)
    
    async def process_message(
        self,
        user_id: int,
        session_id: str,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa mensagem com contexto completo."""
        
        # Enriquecer contexto com memória
        context["conversation_history"] = self.memory_service.get_conversation_context(user_id)
        context["preferences"] = self.memory_service.get_user_preferences(user_id)
        context["learned_facts"] = self.memory_service.get_learned_facts(user_id)
        
        # Processar com agente
        result = await self.ai_agent.process_message(
            user_id=user_id,
            session_id=session_id,
            message=message,
            context=context
        )
        
        # Executar ação
        await self._execute_action(user_id, result)
        
        return result
    
    async def _execute_action(
        self, 
        user_id: int, 
        result: Dict[str, Any]
    ) -> None:
        """Executa ação baseada no resultado do agente."""
        action = result.get("next_action")
        entities = result.get("entities", {})
        
        if action == "create_reminder":
            service = ReminderService(self.db)
            await service.create_from_entities(user_id, entities.get("reminder", {}))
        
        elif action == "create_finance":
            service = FinanceService(self.db)
            await service.create_from_entities(user_id, entities.get("finance", {}))
        
        elif action == "create_meeting":
            service = MeetingService(self.db)
            await service.create_from_entities(
                user_id, 
                entities.get("meeting", {}),
                audio_url=entities.get("audio_url"),
                transcription=entities.get("transcription")
            )
```

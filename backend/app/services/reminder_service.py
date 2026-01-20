import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import RecurrenceType, Reminder
from app.schemas.reminder import ReminderCreate, ReminderFromAI, ReminderUpdate


def utc_now():
    """Retorna datetime atual em UTC."""
    return datetime.now(timezone.utc)


logger = logging.getLogger(__name__)


class ReminderService:
    """Serviço para gerenciamento de lembretes."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, data: ReminderCreate) -> Reminder:
        """
        Cria um novo lembrete.

        Args:
            user_id: ID do usuário
            data: Dados do lembrete

        Returns:
            Reminder: Lembrete criado
        """
        actual_time = data.scheduled_time - timedelta(minutes=data.remind_before_minutes)

        reminder = Reminder(
            user_id=user_id,
            title=data.title,
            description=data.description,
            scheduled_time=data.scheduled_time,
            remind_before_minutes=data.remind_before_minutes,
            actual_reminder_time=actual_time,
            recurrence_type=RecurrenceType(data.recurrence_type.value),
            recurrence_config=data.recurrence_config,
            is_active=True,
            is_completed=False,
            notified=False,
        )

        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)

        logger.info(f"Lembrete criado: {reminder.id} para usuário {user_id}")
        return reminder

    def create_from_entities(self, user_id: int, entities: dict) -> Reminder:
        """
        Cria lembrete a partir de entidades extraídas pela IA.

        Args:
            user_id: ID do usuário
            entities: Entidades extraídas

        Returns:
            Reminder: Lembrete criado
        """
        try:
            scheduled_time = datetime.fromisoformat(entities["scheduled_time"].replace("Z", "+00:00"))
        except:
            scheduled_time = datetime.now()

        data = ReminderCreate(
            title=entities.get("title", "Lembrete"),
            description=entities.get("description"),
            scheduled_time=scheduled_time,
            remind_before_minutes=entities.get("remind_before_minutes", 0),
            recurrence_type=entities.get("recurrence_type", "once"),
        )

        return self.create(user_id, data)

    def get_by_id(self, reminder_id: int, user_id: int) -> Optional[Reminder]:
        """Busca lembrete por ID."""
        return self.db.query(Reminder).filter(and_(Reminder.id == reminder_id, Reminder.user_id == user_id)).first()

    def list_by_user(
        self, user_id: int, status: str = "active", limit: int = 20, offset: int = 0
    ) -> Tuple[List[Reminder], int]:
        """
        Lista lembretes do usuário com paginação.

        Args:
            user_id: ID do usuário
            status: active, completed, all
            limit: Quantidade por página
            offset: Offset para paginação

        Returns:
            Tuple: (lista de lembretes, total)
        """
        query = self.db.query(Reminder).filter(Reminder.user_id == user_id)

        if status == "active":
            query = query.filter(and_(Reminder.is_active == True, Reminder.is_completed == False))
        elif status == "completed":
            query = query.filter(Reminder.is_completed == True)

        total = query.count()

        reminders = query.order_by(Reminder.scheduled_time.asc()).offset(offset).limit(limit).all()

        return reminders, total

    def update(self, reminder_id: int, user_id: int, data: ReminderUpdate) -> Optional[Reminder]:
        """
        Atualiza um lembrete.

        Args:
            reminder_id: ID do lembrete
            user_id: ID do usuário
            data: Dados para atualização

        Returns:
            Reminder atualizado ou None
        """
        reminder = self.get_by_id(reminder_id, user_id)
        if not reminder:
            return None

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field == "recurrence_type" and value:
                value = RecurrenceType(value.value)
            setattr(reminder, field, value)

        if data.scheduled_time or data.remind_before_minutes is not None:
            reminder.actual_reminder_time = reminder.scheduled_time - timedelta(minutes=reminder.remind_before_minutes)
            reminder.notified = False

        reminder.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(reminder)

        logger.info(f"Lembrete atualizado: {reminder_id}")
        return reminder

    def delete(self, reminder_id: int, user_id: int) -> bool:
        """
        Remove lembrete (soft delete).

        Args:
            reminder_id: ID do lembrete
            user_id: ID do usuário

        Returns:
            True se removido, False se não encontrado
        """
        reminder = self.get_by_id(reminder_id, user_id)
        if not reminder:
            return False

        reminder.is_active = False
        reminder.updated_at = utc_now()
        self.db.commit()

        logger.info(f"Lembrete desativado: {reminder_id}")
        return True

    def complete(self, reminder_id: int, user_id: int) -> Optional[Reminder]:
        """
        Marca lembrete como concluído.

        Args:
            reminder_id: ID do lembrete
            user_id: ID do usuário

        Returns:
            Reminder atualizado ou None
        """
        reminder = self.get_by_id(reminder_id, user_id)
        if not reminder:
            return None

        reminder.is_completed = True
        reminder.is_active = False
        reminder.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(reminder)

        logger.info(f"Lembrete concluído: {reminder_id}")
        return reminder

    def get_upcoming(self, user_id: int, hours: int = 24) -> List[Reminder]:
        """
        Retorna lembretes das próximas N horas.

        Args:
            user_id: ID do usuário
            hours: Quantidade de horas

        Returns:
            Lista de lembretes
        """
        now = utc_now()
        end = now + timedelta(hours=hours)

        return (
            self.db.query(Reminder)
            .filter(
                and_(
                    Reminder.user_id == user_id,
                    Reminder.is_active == True,
                    Reminder.is_completed == False,
                    Reminder.actual_reminder_time >= now,
                    Reminder.actual_reminder_time <= end,
                )
            )
            .order_by(Reminder.actual_reminder_time.asc())
            .all()
        )

    def get_pending_notifications(self) -> List[Reminder]:
        """
        Retorna lembretes pendentes de notificação.
        Usado pelo scheduler.

        Returns:
            Lista de lembretes para notificar
        """
        now = utc_now()

        return (
            self.db.query(Reminder)
            .filter(and_(Reminder.is_active == True, Reminder.notified == False, Reminder.actual_reminder_time <= now))
            .all()
        )

    def count_by_user(self, user_id: int) -> dict:
        """
        Conta lembretes por status.

        Args:
            user_id: ID do usuário

        Returns:
            Dict com contagens
        """
        total = self.db.query(func.count(Reminder.id)).filter(Reminder.user_id == user_id).scalar()

        active = (
            self.db.query(func.count(Reminder.id))
            .filter(and_(Reminder.user_id == user_id, Reminder.is_active == True, Reminder.is_completed == False))
            .scalar()
        )

        completed = (
            self.db.query(func.count(Reminder.id))
            .filter(and_(Reminder.user_id == user_id, Reminder.is_completed == True))
            .scalar()
        )

        return {"total": total, "active": active, "completed": completed}

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytz
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import (
    RecurrenceType,
    Reminder,
    ScheduledMessage,
    ScheduledMessageStatus,
    Task,
    TaskStatus,
    User,
)
from app.services.whatsapp_service import WhatsAppService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReminderScheduler:
    def __init__(self):
        self.whatsapp_service = WhatsAppService(
            account_sid=settings.TWILIO_ACCOUNT_SID,
            auth_token=settings.TWILIO_AUTH_TOKEN,
            whatsapp_number=settings.TWILIO_WHATSAPP_NUMBER,
        )
        self.running = False

    def get_pending_reminders(self, db: Session) -> list[Reminder]:
        """Busca lembretes pendentes para notificar"""
        now = datetime.now(timezone.utc)

        reminders = (
            db.query(Reminder)
            .filter(and_(Reminder.is_active == True, Reminder.notified == False, Reminder.actual_reminder_time <= now))
            .all()
        )

        return reminders

    def format_reminder_message(self, reminder: Reminder, user: User) -> str:
        """Formata a mensagem do lembrete"""

        # Converter para timezone do usuário
        user_tz = pytz.timezone(user.timezone)
        scheduled_time = reminder.scheduled_time.replace(tzinfo=pytz.utc).astimezone(user_tz)

        time_str = scheduled_time.strftime("%H:%M")
        date_str = scheduled_time.strftime("%d/%m/%Y")

        message = f"🔔 *Lembrete*\n\n"
        message += f"📌 {reminder.title}\n"

        if reminder.description:
            message += f"\n{reminder.description}\n"

        message += f"\n⏰ Horário: {time_str}"

        # Se for hoje, não mostrar a data
        today = datetime.now(user_tz).date()
        if scheduled_time.date() != today:
            message += f" - {date_str}"

        return message

    async def send_reminder(self, reminder: Reminder, user: User, db: Session):
        """Envia o lembrete para o usuário"""
        try:
            message = self.format_reminder_message(reminder, user)

            result = self.whatsapp_service.send_message(to_number=user.phone_number, message=message)

            if result["success"]:
                reminder.notified = True
                reminder.notified_at = datetime.now(timezone.utc)

                # Se for recorrente, criar próxima ocorrência
                if reminder.recurrence_type != RecurrenceType.ONCE:
                    self.create_next_occurrence(reminder, db)
                else:
                    reminder.is_completed = True

                db.commit()
                logger.info(f"Lembrete {reminder.id} enviado para usuário {user.id}")
            else:
                logger.error(f"Erro ao enviar lembrete {reminder.id}: {result.get('error')}")

        except Exception as e:
            logger.error(f"Erro ao processar lembrete {reminder.id}: {e}")

    def create_next_occurrence(self, reminder: Reminder, db: Session):
        """Cria a próxima ocorrência de um lembrete recorrente"""
        next_time = None

        if reminder.recurrence_type == RecurrenceType.DAILY:
            next_time = reminder.scheduled_time + timedelta(days=1)

        elif reminder.recurrence_type == RecurrenceType.WEEKDAYS:
            # Segunda a Sexta
            next_time = reminder.scheduled_time + timedelta(days=1)
            while next_time.weekday() >= 5:  # 5=Sábado, 6=Domingo
                next_time += timedelta(days=1)

        elif reminder.recurrence_type == RecurrenceType.WEEKENDS:
            # Sábado e Domingo
            next_time = reminder.scheduled_time + timedelta(days=1)
            while next_time.weekday() < 5:
                next_time += timedelta(days=1)

        elif reminder.recurrence_type == RecurrenceType.WEEKLY:
            next_time = reminder.scheduled_time + timedelta(weeks=1)

        elif reminder.recurrence_type == RecurrenceType.MONTHLY:
            # Mesmo dia do próximo mês
            current = reminder.scheduled_time
            if current.month == 12:
                next_time = current.replace(year=current.year + 1, month=1)
            else:
                next_time = current.replace(month=current.month + 1)

        elif reminder.recurrence_type == RecurrenceType.YEARLY:
            next_time = reminder.scheduled_time.replace(year=reminder.scheduled_time.year + 1)

        if next_time:
            new_reminder = Reminder(
                user_id=reminder.user_id,
                title=reminder.title,
                description=reminder.description,
                scheduled_time=next_time,
                remind_before_minutes=reminder.remind_before_minutes,
                actual_reminder_time=next_time - timedelta(minutes=reminder.remind_before_minutes),
                recurrence_type=reminder.recurrence_type,
                recurrence_config=reminder.recurrence_config,
                is_active=True,
                is_completed=False,
                notified=False,
            )

            db.add(new_reminder)
            db.commit()
            logger.info(f"Nova ocorrência criada: {new_reminder.id} para {next_time}")

    async def process_reminders(self):
        """Processa todos os lembretes pendentes"""
        db = SessionLocal()

        try:
            reminders = self.get_pending_reminders(db)
            if reminders:
                logger.info(f"📋 Processando {len(reminders)} lembretes pendentes")

            for reminder in reminders:
                user = db.query(User).filter(User.id == reminder.user_id).first()
                if user:
                    await self.send_reminder(reminder, user, db)

        finally:
            db.close()

    def get_pending_scheduled_messages(self, db: Session) -> list[ScheduledMessage]:
        """Busca mensagens agendadas pendentes para envio"""
        now = datetime.now(timezone.utc)

        messages = (
            db.query(ScheduledMessage)
            .filter(
                and_(ScheduledMessage.status == ScheduledMessageStatus.PENDING, ScheduledMessage.scheduled_time <= now)
            )
            .all()
        )

        return messages

    async def send_scheduled_message(self, scheduled_msg: ScheduledMessage, user: User, db: Session):
        """Envia uma mensagem agendada"""
        try:
            # Determinar destinatário
            if scheduled_msg.recipient_phone:
                recipient_phone = scheduled_msg.recipient_phone
                recipient_name = scheduled_msg.recipient_name or "Contato"
            else:
                scheduled_msg.status = ScheduledMessageStatus.FAILED
                scheduled_msg.error_message = "Nenhum destinatário definido"
                db.commit()
                return

            # Enviar mensagem
            result = self.whatsapp_service.send_message(to_number=recipient_phone, message=scheduled_msg.message)

            if result.get("success"):
                scheduled_msg.status = ScheduledMessageStatus.SENT
                scheduled_msg.sent_at = datetime.now(timezone.utc)
                logger.info(f"Mensagem agendada {scheduled_msg.id} enviada para {recipient_name}")

                # Se for recorrente, criar próxima ocorrência
                if scheduled_msg.recurrence_type != RecurrenceType.ONCE:
                    self.create_next_scheduled_message(scheduled_msg, db)
            else:
                scheduled_msg.status = ScheduledMessageStatus.FAILED
                scheduled_msg.error_message = result.get("error", "Erro desconhecido")
                logger.error(f"Erro ao enviar mensagem agendada {scheduled_msg.id}: {result.get('error')}")

            db.commit()

        except Exception as e:
            scheduled_msg.status = ScheduledMessageStatus.FAILED
            scheduled_msg.error_message = str(e)
            db.commit()
            logger.error(f"Erro ao processar mensagem agendada {scheduled_msg.id}: {e}")

    def create_next_scheduled_message(self, original: ScheduledMessage, db: Session):
        """Cria a próxima ocorrência de uma mensagem recorrente"""
        next_time = None

        if original.recurrence_type == RecurrenceType.DAILY:
            next_time = original.scheduled_time + timedelta(days=1)
        elif original.recurrence_type == RecurrenceType.WEEKLY:
            next_time = original.scheduled_time + timedelta(weeks=1)
        elif original.recurrence_type == RecurrenceType.MONTHLY:
            current = original.scheduled_time
            if current.month == 12:
                next_time = current.replace(year=current.year + 1, month=1)
            else:
                next_time = current.replace(month=current.month + 1)

        if next_time:
            new_msg = ScheduledMessage(
                user_id=original.user_id,
                contact_id=original.contact_id,
                recipient_phone=original.recipient_phone,
                recipient_name=original.recipient_name,
                group_name=original.group_name,
                message=original.message,
                scheduled_time=next_time,
                status=ScheduledMessageStatus.PENDING,
                recurrence_type=original.recurrence_type,
            )
            db.add(new_msg)
            db.commit()
            logger.info(f"Próxima mensagem agendada criada: {new_msg.id} para {next_time}")

    async def process_scheduled_messages(self):
        """Processa todas as mensagens agendadas pendentes"""
        db = SessionLocal()

        try:
            messages = self.get_pending_scheduled_messages(db)
            if messages:
                logger.info(f"📨 Processando {len(messages)} mensagens agendadas")

            for msg in messages:
                user = db.query(User).filter(User.id == msg.user_id).first()
                if user:
                    await self.send_scheduled_message(msg, user, db)

        finally:
            db.close()

    # ==================== TASKS ====================

    def get_pending_task_notifications(self, db: Session) -> list[Task]:
        """Busca tarefas que precisam de notificação."""
        now = datetime.now(timezone.utc)

        tasks = (
            db.query(Task)
            .filter(
                and_(
                    Task.is_active == True,
                    Task.notified == False,
                    Task.due_date != None,
                    Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED]),
                )
            )
            .all()
        )

        # Filtrar apenas as que estão dentro do tempo de notificação
        return [t for t in tasks if t.due_date and (t.due_date - timedelta(minutes=t.remind_before_minutes)) <= now]

    def format_task_message(self, task: Task, user: User) -> str:
        """Formata a mensagem de notificação da tarefa."""
        user_tz = pytz.timezone(user.timezone)

        priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "urgent": "🔴"}
        emoji = priority_emoji.get(task.priority.value, "📋")

        message = f"{emoji} *Lembrete de Tarefa*\n\n"
        message += f"📌 {task.title}\n"

        if task.description:
            message += f"\n{task.description[:200]}\n"

        if task.due_date:
            due_local = task.due_date.replace(tzinfo=pytz.utc).astimezone(user_tz)
            message += f"\n⏰ Vencimento: {due_local.strftime('%d/%m/%Y às %H:%M')}"

        return message

    async def send_task_notification(self, task: Task, user: User, db: Session):
        """Envia notificação de tarefa para o usuário."""
        try:
            message = self.format_task_message(task, user)

            result = self.whatsapp_service.send_message(to_number=user.phone_number, message=message)

            if result["success"]:
                task.notified = True
                db.commit()
                logger.info(f"Notificação de tarefa {task.id} enviada para usuário {user.id}")
            else:
                logger.error(f"Erro ao enviar notificação de tarefa {task.id}: {result.get('error')}")

        except Exception as e:
            logger.error(f"Erro ao processar notificação de tarefa {task.id}: {e}")

    async def process_task_notifications(self):
        """Processa notificações de tarefas pendentes."""
        db = SessionLocal()

        try:
            tasks = self.get_pending_task_notifications(db)
            if tasks:
                logger.info(f"📋 Processando {len(tasks)} notificações de tarefas")

            for task in tasks:
                user = db.query(User).filter(User.id == task.user_id).first()
                if user:
                    await self.send_task_notification(task, user, db)

        finally:
            db.close()

    async def run(self):
        """Loop principal do scheduler"""
        self.running = True
        self._cycle_count = 0
        self._heartbeat_interval = 60  # Log de status a cada 60 ciclos (~5 min)
        logger.info("🚀 Scheduler iniciado - monitorando lembretes, tarefas e mensagens agendadas")

        while self.running:
            try:
                await self.process_reminders()
                await self.process_task_notifications()
                await self.process_scheduled_messages()

                # Heartbeat periódico para confirmar que está rodando
                self._cycle_count += 1
                if self._cycle_count >= self._heartbeat_interval:
                    logger.info("💓 Scheduler ativo - aguardando tarefas")
                    self._cycle_count = 0

                await asyncio.sleep(settings.SCHEDULER_CHECK_INTERVAL_SECONDS)

            except Exception as e:
                logger.error(f"❌ Erro no scheduler: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Para o scheduler"""
        self.running = False
        logger.info("Scheduler parado")


async def main():
    scheduler = ReminderScheduler()
    await scheduler.run()


if __name__ == "__main__":
    asyncio.run(main())

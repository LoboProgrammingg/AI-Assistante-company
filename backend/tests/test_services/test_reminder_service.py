"""
Testes para ReminderService.
"""
import pytest
from datetime import datetime, timedelta

from app.services import ReminderService
from app.schemas import ReminderCreate, ReminderUpdate, RecurrenceTypeEnum
from app.models import User, Reminder


class TestReminderServiceCreate:
    """Testes de criação de lembretes."""

    def test_create_reminder_success(self, db, sample_user):
        """Deve criar um lembrete com sucesso."""
        service = ReminderService(db)
        
        data = ReminderCreate(
            title="Reunião importante",
            description="Reunião com cliente",
            scheduled_time=datetime(2026, 1, 25, 14, 0, 0),
            remind_before_minutes=60,
            recurrence_type=RecurrenceTypeEnum.ONCE,
        )
        
        reminder = service.create(sample_user.id, data)
        
        assert reminder.id is not None
        assert reminder.title == "Reunião importante"
        assert reminder.user_id == sample_user.id
        assert reminder.is_active is True
        assert reminder.is_completed is False

    def test_create_reminder_calculates_actual_time(self, db, sample_user):
        """Deve calcular actual_reminder_time corretamente."""
        service = ReminderService(db)
        
        scheduled = datetime(2026, 1, 25, 14, 0, 0)
        
        data = ReminderCreate(
            title="Teste",
            scheduled_time=scheduled,
            remind_before_minutes=30,
        )
        
        reminder = service.create(sample_user.id, data)
        
        expected_actual = scheduled - timedelta(minutes=30)
        assert reminder.actual_reminder_time == expected_actual

    def test_create_reminder_with_recurrence(self, db, sample_user):
        """Deve criar lembrete recorrente."""
        service = ReminderService(db)
        
        data = ReminderCreate(
            title="Standup diário",
            scheduled_time=datetime(2026, 1, 25, 9, 0, 0),
            recurrence_type=RecurrenceTypeEnum.WEEKDAYS,
        )
        
        reminder = service.create(sample_user.id, data)
        
        assert reminder.recurrence_type.value == "weekdays"


class TestReminderServiceRead:
    """Testes de leitura de lembretes."""

    def test_get_by_id_success(self, db, sample_user, sample_reminder):
        """Deve buscar lembrete por ID."""
        service = ReminderService(db)
        
        reminder = service.get_by_id(sample_reminder.id, sample_user.id)
        
        assert reminder is not None
        assert reminder.id == sample_reminder.id

    def test_get_by_id_wrong_user(self, db, sample_user, sample_user_2, sample_reminder):
        """Não deve retornar lembrete de outro usuário."""
        service = ReminderService(db)
        
        reminder = service.get_by_id(sample_reminder.id, sample_user_2.id)
        
        assert reminder is None

    def test_get_by_id_not_found(self, db, sample_user):
        """Deve retornar None para ID inexistente."""
        service = ReminderService(db)
        
        reminder = service.get_by_id(99999, sample_user.id)
        
        assert reminder is None

    def test_list_by_user_active(self, db, sample_user, sample_reminder):
        """Deve listar apenas lembretes ativos."""
        service = ReminderService(db)
        
        reminders, total = service.list_by_user(sample_user.id, status="active")
        
        assert total >= 1
        assert all(r.is_active for r in reminders)

    def test_list_by_user_pagination(self, db, sample_user):
        """Deve respeitar paginação."""
        service = ReminderService(db)
        
        for i in range(5):
            data = ReminderCreate(
                title=f"Lembrete {i}",
                scheduled_time=datetime(2026, 1, 25, 10 + i, 0, 0),
            )
            service.create(sample_user.id, data)
        
        reminders, total = service.list_by_user(
            sample_user.id,
            status="all",
            limit=2,
            offset=0
        )
        
        assert len(reminders) == 2
        assert total == 5


class TestReminderServiceUpdate:
    """Testes de atualização de lembretes."""

    def test_update_reminder_success(self, db, sample_user, sample_reminder):
        """Deve atualizar lembrete com sucesso."""
        service = ReminderService(db)
        
        data = ReminderUpdate(title="Título Atualizado")
        
        updated = service.update(sample_reminder.id, sample_user.id, data)
        
        assert updated is not None
        assert updated.title == "Título Atualizado"

    def test_update_reminder_recalculates_actual_time(self, db, sample_user, sample_reminder):
        """Deve recalcular actual_time ao atualizar horário."""
        service = ReminderService(db)
        
        new_time = datetime(2026, 2, 1, 15, 0, 0)
        data = ReminderUpdate(
            scheduled_time=new_time,
            remind_before_minutes=15
        )
        
        updated = service.update(sample_reminder.id, sample_user.id, data)
        
        expected_actual = new_time - timedelta(minutes=15)
        assert updated.actual_reminder_time == expected_actual

    def test_update_reminder_not_found(self, db, sample_user):
        """Deve retornar None para lembrete inexistente."""
        service = ReminderService(db)
        
        data = ReminderUpdate(title="Novo Título")
        
        result = service.update(99999, sample_user.id, data)
        
        assert result is None


class TestReminderServiceDelete:
    """Testes de remoção de lembretes."""

    def test_delete_reminder_success(self, db, sample_user, sample_reminder):
        """Deve desativar lembrete (soft delete)."""
        service = ReminderService(db)
        
        result = service.delete(sample_reminder.id, sample_user.id)
        
        assert result is True
        
        reminder = service.get_by_id(sample_reminder.id, sample_user.id)
        assert reminder.is_active is False

    def test_delete_reminder_not_found(self, db, sample_user):
        """Deve retornar False para ID inexistente."""
        service = ReminderService(db)
        
        result = service.delete(99999, sample_user.id)
        
        assert result is False


class TestReminderServiceComplete:
    """Testes de conclusão de lembretes."""

    def test_complete_reminder_success(self, db, sample_user, sample_reminder):
        """Deve marcar lembrete como concluído."""
        service = ReminderService(db)
        
        completed = service.complete(sample_reminder.id, sample_user.id)
        
        assert completed is not None
        assert completed.is_completed is True
        assert completed.is_active is False


class TestReminderServiceUpcoming:
    """Testes de lembretes próximos."""

    def test_get_upcoming_returns_future_reminders(self, db, sample_user):
        """Deve retornar lembretes nas próximas horas."""
        service = ReminderService(db)
        
        now = datetime.utcnow()
        
        data = ReminderCreate(
            title="Lembrete próximo",
            scheduled_time=now + timedelta(hours=2),
            remind_before_minutes=0,
        )
        service.create(sample_user.id, data)
        
        upcoming = service.get_upcoming(sample_user.id, hours=24)
        
        assert len(upcoming) >= 1


class TestReminderServiceCount:
    """Testes de contagem."""

    def test_count_by_user(self, db, sample_user, sample_reminder):
        """Deve contar lembretes por status."""
        service = ReminderService(db)
        
        counts = service.count_by_user(sample_user.id)
        
        assert "total" in counts
        assert "active" in counts
        assert "completed" in counts
        assert counts["total"] >= 1

"""
Testes para MeetingService.
"""
import pytest
from datetime import datetime

from app.services import MeetingService
from app.schemas import MeetingCreate, MeetingUpdate, ActionItem
from app.models import User, Meeting


class TestMeetingServiceCreate:
    """Testes de criação de reuniões."""

    def test_create_meeting_success(self, db, sample_user):
        """Deve criar reunião com sucesso."""
        service = MeetingService(db)
        
        data = MeetingCreate(
            title="Reunião de Sprint",
            date=datetime.now(),
            duration_minutes=30,
            summary="Discussão sobre entregas da sprint.",
            key_topics=["Backend", "Frontend"],
            participants=["João", "Maria"],
        )
        
        meeting = service.create(sample_user.id, data)
        
        assert meeting.id is not None
        assert meeting.title == "Reunião de Sprint"
        assert meeting.user_id == sample_user.id

    def test_create_meeting_with_action_items(self, db, sample_user):
        """Deve criar reunião com action items."""
        service = MeetingService(db)
        
        data = MeetingCreate(
            title="Planning",
            action_items=[
                ActionItem(task="Revisar código", responsible="João"),
                ActionItem(task="Atualizar docs", responsible="Maria"),
            ],
        )
        
        meeting = service.create(sample_user.id, data)
        
        assert len(meeting.action_items) == 2


class TestMeetingServiceRead:
    """Testes de leitura de reuniões."""

    def test_get_by_id_success(self, db, sample_user, sample_meeting):
        """Deve buscar reunião por ID."""
        service = MeetingService(db)
        
        meeting = service.get_by_id(sample_meeting.id, sample_user.id)
        
        assert meeting is not None
        assert meeting.id == sample_meeting.id

    def test_get_by_id_wrong_user(self, db, sample_user_2, sample_meeting):
        """Não deve retornar reunião de outro usuário."""
        service = MeetingService(db)
        
        meeting = service.get_by_id(sample_meeting.id, sample_user_2.id)
        
        assert meeting is None

    def test_list_by_user(self, db, sample_user, sample_meeting):
        """Deve listar reuniões do usuário."""
        service = MeetingService(db)
        
        meetings, total = service.list_by_user(sample_user.id)
        
        assert total >= 1
        assert all(m.user_id == sample_user.id for m in meetings)


class TestMeetingServiceUpdate:
    """Testes de atualização de reuniões."""

    def test_update_title_success(self, db, sample_user, sample_meeting):
        """Deve atualizar título da reunião."""
        service = MeetingService(db)
        
        data = MeetingUpdate(title="Título Atualizado")
        
        updated = service.update(sample_meeting.id, sample_user.id, data)
        
        assert updated is not None
        assert updated.title == "Título Atualizado"

    def test_update_summary(self, db, sample_user, sample_meeting):
        """Deve atualizar resumo."""
        service = MeetingService(db)
        
        data = MeetingUpdate(summary="Novo resumo da reunião.")
        
        updated = service.update(sample_meeting.id, sample_user.id, data)
        
        assert updated.summary == "Novo resumo da reunião."


class TestMeetingServiceDelete:
    """Testes de remoção de reuniões."""

    def test_delete_success(self, db, sample_user, sample_meeting):
        """Deve remover reunião."""
        service = MeetingService(db)
        
        result = service.delete(sample_meeting.id, sample_user.id)
        
        assert result is True
        
        meeting = service.get_by_id(sample_meeting.id, sample_user.id)
        assert meeting is None


class TestMeetingServiceSearch:
    """Testes de busca."""

    def test_search_by_title(self, db, sample_user, sample_meeting):
        """Deve buscar por título."""
        service = MeetingService(db)
        
        results = service.search(sample_user.id, "Planejamento")
        
        assert len(results) >= 1

    def test_search_by_summary(self, db, sample_user, sample_meeting):
        """Deve buscar por resumo."""
        service = MeetingService(db)
        
        results = service.search(sample_user.id, "próximos passos")
        
        assert len(results) >= 1

    def test_search_no_results(self, db, sample_user):
        """Deve retornar lista vazia para termo não encontrado."""
        service = MeetingService(db)
        
        results = service.search(sample_user.id, "xyzabc123")
        
        assert len(results) == 0


class TestMeetingServiceActionItems:
    """Testes de action items."""

    def test_update_action_item_status(self, db, sample_user, sample_meeting):
        """Deve atualizar status de action item."""
        service = MeetingService(db)
        
        updated = service.update_action_item_status(
            sample_meeting.id,
            sample_user.id,
            item_index=0,
            status="completed"
        )
        
        assert updated is not None
        assert updated.action_items[0]["status"] == "completed"

    def test_get_action_items_pending(self, db, sample_user, sample_meeting):
        """Deve retornar action items pendentes."""
        service = MeetingService(db)
        
        pending = service.get_action_items_pending(sample_user.id)
        
        assert len(pending) >= 1
        assert all(item.get("status", "pending") == "pending" for item in pending)

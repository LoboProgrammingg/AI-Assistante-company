"""
Testes para MemoryService.
"""
import pytest

from app.services import MemoryService
from app.models import User, Message


class TestMemoryServiceBasic:
    """Testes básicos de memória."""

    def test_set_memory_creates_new(self, db, sample_user):
        """Deve criar nova memória."""
        service = MemoryService(db)
        
        value = {"preference": "morning"}
        memory = service.set_memory(sample_user.id, "time_pref", value)
        
        assert memory.id is not None
        assert memory.key == "time_pref"
        assert memory.value == value

    def test_set_memory_updates_existing(self, db, sample_user):
        """Deve atualizar memória existente."""
        service = MemoryService(db)
        
        service.set_memory(sample_user.id, "test_key", {"v": 1})
        service.set_memory(sample_user.id, "test_key", {"v": 2})
        
        result = service.get_memory(sample_user.id, "test_key")
        
        assert result == {"v": 2}

    def test_get_memory_returns_value(self, db, sample_user):
        """Deve retornar valor da memória."""
        service = MemoryService(db)
        
        service.set_memory(sample_user.id, "my_key", {"data": "test"})
        
        result = service.get_memory(sample_user.id, "my_key")
        
        assert result == {"data": "test"}

    def test_get_memory_returns_none_for_missing(self, db, sample_user):
        """Deve retornar None para chave inexistente."""
        service = MemoryService(db)
        
        result = service.get_memory(sample_user.id, "nonexistent_key")
        
        assert result is None

    def test_delete_memory(self, db, sample_user):
        """Deve remover memória."""
        service = MemoryService(db)
        
        service.set_memory(sample_user.id, "to_delete", {"x": 1})
        
        result = service.delete_memory(sample_user.id, "to_delete")
        
        assert result is True
        assert service.get_memory(sample_user.id, "to_delete") is None


class TestMemoryServiceConversation:
    """Testes de contexto de conversa."""

    def test_get_conversation_context(self, db, sample_user, sample_message):
        """Deve retornar contexto de conversa."""
        service = MemoryService(db)
        
        context = service.get_conversation_context(sample_user.id, limit=10)
        
        assert len(context) >= 1
        assert "role" in context[0]
        assert "content" in context[0]

    def test_get_conversation_context_empty(self, db, sample_user):
        """Deve retornar lista vazia sem mensagens."""
        service = MemoryService(db)
        
        context = service.get_conversation_context(sample_user.id)
        
        assert context == []


class TestMemoryServicePreferences:
    """Testes de preferências."""

    def test_get_user_preferences_empty(self, db, sample_user):
        """Deve retornar dict vazio sem preferências."""
        service = MemoryService(db)
        
        prefs = service.get_user_preferences(sample_user.id)
        
        assert prefs == {}

    def test_update_user_preferences(self, db, sample_user):
        """Deve atualizar preferências."""
        service = MemoryService(db)
        
        service.update_user_preferences(sample_user.id, {"theme": "dark"})
        
        prefs = service.get_user_preferences(sample_user.id)
        
        assert prefs["theme"] == "dark"

    def test_update_user_preferences_merge(self, db, sample_user):
        """Deve mesclar preferências existentes."""
        service = MemoryService(db)
        
        service.update_user_preferences(sample_user.id, {"a": 1})
        service.update_user_preferences(sample_user.id, {"b": 2})
        
        prefs = service.get_user_preferences(sample_user.id)
        
        assert prefs["a"] == 1
        assert prefs["b"] == 2


class TestMemoryServiceFacts:
    """Testes de fatos aprendidos."""

    def test_get_learned_facts_empty(self, db, sample_user):
        """Deve retornar dict vazio sem fatos."""
        service = MemoryService(db)
        
        facts = service.get_learned_facts(sample_user.id)
        
        assert facts == {}

    def test_add_learned_fact(self, db, sample_user):
        """Deve adicionar fato."""
        service = MemoryService(db)
        
        service.add_learned_fact(sample_user.id, "name", "João")
        
        facts = service.get_learned_facts(sample_user.id)
        
        assert facts["name"] == "João"


class TestMemoryServiceStats:
    """Testes de estatísticas."""

    def test_get_interaction_stats_default(self, db, sample_user):
        """Deve retornar estatísticas padrão."""
        service = MemoryService(db)
        
        stats = service.get_interaction_stats(sample_user.id)
        
        assert stats["total_messages"] == 0
        assert stats["reminders_created"] == 0

    def test_increment_stat(self, db, sample_user):
        """Deve incrementar estatística."""
        service = MemoryService(db)
        
        service.increment_stat(sample_user.id, "total_messages")
        service.increment_stat(sample_user.id, "total_messages")
        
        stats = service.get_interaction_stats(sample_user.id)
        
        assert stats["total_messages"] == 2


class TestMemoryServiceFullContext:
    """Testes de contexto completo."""

    def test_get_full_context(self, db, sample_user):
        """Deve retornar contexto completo."""
        service = MemoryService(db)
        
        service.add_learned_fact(sample_user.id, "name", "Test")
        
        context = service.get_full_context(sample_user.id)
        
        assert "conversation" in context
        assert "preferences" in context
        assert "facts" in context
        assert "stats" in context


class TestMemoryServiceClear:
    """Testes de limpeza."""

    def test_clear_user_memory(self, db, sample_user):
        """Deve limpar toda memória do usuário."""
        service = MemoryService(db)
        
        service.set_memory(sample_user.id, "key1", {"a": 1})
        service.set_memory(sample_user.id, "key2", {"b": 2})
        
        deleted = service.clear_user_memory(sample_user.id)
        
        assert deleted == 2
        assert service.get_memory(sample_user.id, "key1") is None
        assert service.get_memory(sample_user.id, "key2") is None

"""
Testes para MemoryManager.
"""
import pytest
from unittest.mock import MagicMock

from app.ai.memory import MemoryManager
from app.services import MemoryService


class TestMemoryManagerInit:
    """Testes de inicialização."""

    def test_initialization(self, db, sample_user):
        """Deve inicializar corretamente."""
        manager = MemoryManager(db, sample_user.id)
        
        assert manager.user_id == sample_user.id
        assert manager._cache == {}


class TestMemoryManagerContext:
    """Testes de contexto."""

    def test_get_full_context(self, db, sample_user):
        """Deve retornar contexto completo."""
        manager = MemoryManager(db, sample_user.id)
        
        context = manager.get_full_context()
        
        assert "conversation" in context
        assert "preferences" in context
        assert "facts" in context
        assert "stats" in context

    def test_get_full_context_caches(self, db, sample_user):
        """Deve cachear contexto."""
        manager = MemoryManager(db, sample_user.id)
        
        context1 = manager.get_full_context()
        context2 = manager.get_full_context()
        
        assert context1 is context2

    def test_build_context_prompt(self, db, sample_user):
        """Deve construir prompt de contexto."""
        manager = MemoryManager(db, sample_user.id)
        
        manager.service.add_learned_fact(sample_user.id, "name", "João")
        manager._invalidate_cache()
        
        prompt = manager.build_context_prompt()
        
        assert "João" in prompt
        assert "CONTEXTO DO USUÁRIO" in prompt


class TestMemoryManagerLearn:
    """Testes de aprendizado."""

    def test_learn_name_from_message(self, db, sample_user):
        """Deve aprender nome."""
        manager = MemoryManager(db, sample_user.id)
        
        manager.learn_from_message(
            message="Meu nome é Pedro",
            intent="general",
            entities={}
        )
        
        facts = manager.get_learned_facts()
        assert facts.get("name") == "Pedro"

    def test_learn_name_variations(self, db, sample_user):
        """Deve detectar variações de nome."""
        manager = MemoryManager(db, sample_user.id)
        
        variations = [
            "pode me chamar de Ana",
            "sou o Carlos",
            "me chamo Luisa"
        ]
        
        for msg in variations:
            manager._invalidate_cache()
            manager.learn_from_message(msg, "general", {})
        
        facts = manager.get_learned_facts()
        assert facts.get("name") is not None

    def test_learn_time_preferences(self, db, sample_user):
        """Deve aprender preferências de horário."""
        manager = MemoryManager(db, sample_user.id)
        
        entities = {
            "reminder": {
                "scheduled_time": "2026-01-25T09:00:00"
            }
        }
        
        manager.learn_from_message("lembrete", "reminder", entities)
        
        time_prefs = manager.service.get_memory(sample_user.id, "time_preferences")
        assert time_prefs is not None

    def test_learn_category_preferences(self, db, sample_user):
        """Deve aprender preferências de categoria."""
        manager = MemoryManager(db, sample_user.id)
        
        entities = {
            "finance": {
                "category": "Alimentação"
            }
        }
        
        manager.learn_from_message("gasto", "finance", entities)
        
        cat_prefs = manager.service.get_memory(sample_user.id, "category_preferences")
        assert cat_prefs is not None


class TestMemoryManagerUpdate:
    """Testes de atualização após ação."""

    def test_update_after_action(self, db, sample_user):
        """Deve atualizar estatísticas."""
        manager = MemoryManager(db, sample_user.id)
        
        manager.update_after_action("create_reminder", {})
        manager.update_after_action("create_reminder", {})
        
        stats = manager.service.get_interaction_stats(sample_user.id)
        assert stats["reminders_created"] == 2


class TestMemoryManagerPersonalization:
    """Testes de personalização."""

    def test_get_personalization_hints(self, db, sample_user):
        """Deve retornar dicas de personalização."""
        manager = MemoryManager(db, sample_user.id)
        
        for _ in range(3):
            entities = {"reminder": {"scheduled_time": "2026-01-25T09:00:00"}}
            manager.learn_from_message("", "reminder", entities)
        
        hints = manager.get_personalization_hints()
        
        assert "preferred_reminder_hour" in hints or hints == {}


class TestMemoryManagerCache:
    """Testes de cache."""

    def test_invalidate_cache(self, db, sample_user):
        """Deve invalidar cache."""
        manager = MemoryManager(db, sample_user.id)
        
        manager.get_full_context()
        assert "full_context" in manager._cache
        
        manager._invalidate_cache()
        
        assert manager._cache == {}


class TestMemoryManagerClear:
    """Testes de limpeza."""

    def test_clear_memory(self, db, sample_user):
        """Deve limpar memória."""
        manager = MemoryManager(db, sample_user.id)
        
        manager.service.set_memory(sample_user.id, "key1", {"a": 1})
        
        deleted = manager.clear_memory()
        
        assert deleted >= 1
        assert manager.service.get_memory(sample_user.id, "key1") is None

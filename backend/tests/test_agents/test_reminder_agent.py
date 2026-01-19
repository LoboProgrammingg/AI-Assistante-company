"""
Testes para ReminderAgent.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import json

from app.ai.agents import ReminderAgent


class TestReminderAgentInit:
    """Testes de inicialização."""

    def test_agent_initialization(self):
        """Deve inicializar corretamente."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = ReminderAgent()
            
            assert agent.name == "ReminderAgent"
            assert "lembretes" in agent.description.lower()

    def test_system_prompt_contains_recurrence_types(self):
        """System prompt deve conter tipos de recorrência."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = ReminderAgent()
            
            prompt = agent.system_prompt
            assert "once" in prompt
            assert "daily" in prompt
            assert "weekly" in prompt


class TestReminderAgentProcess:
    """Testes de processamento."""

    @pytest.mark.asyncio
    async def test_process_creates_reminder(self):
        """Deve processar e criar lembrete."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI') as mock_llm:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=MagicMock(
                content=json.dumps({
                    "title": "Reunião",
                    "scheduled_time": "2026-01-25T14:00:00",
                    "remind_before_minutes": 30,
                    "recurrence_type": "once",
                    "confidence": 0.9,
                    "needs_clarification": False
                })
            ))
            mock_llm.return_value = mock_instance
            
            agent = ReminderAgent()
            agent.llm = mock_instance
            
            result = await agent.process(
                message="Me lembre da reunião amanhã às 14h",
                context={"timezone": "America/Sao_Paulo"}
            )
            
            assert result["next_action"] == "create_reminder"
            assert "reminder" in result["entities"]

    @pytest.mark.asyncio
    async def test_process_asks_clarification(self):
        """Deve pedir esclarecimento quando necessário."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI') as mock_llm:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=MagicMock(
                content=json.dumps({
                    "needs_clarification": True,
                    "clarification_question": "Qual horário você prefere?"
                })
            ))
            mock_llm.return_value = mock_instance
            
            agent = ReminderAgent()
            agent.llm = mock_instance
            
            result = await agent.process(
                message="Me lembre de algo",
                context={}
            )
            
            assert result["next_action"] == "await_clarification"
            assert "Qual horário" in result["response"]


class TestReminderAgentFormatContext:
    """Testes de formatação de contexto."""

    def test_format_context_with_user_name(self):
        """Deve formatar contexto com nome."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = ReminderAgent()
            
            context = {"user_name": "João", "timezone": "America/Sao_Paulo"}
            formatted = agent.format_context(context)
            
            assert "João" in formatted
            assert "America/Sao_Paulo" in formatted

    def test_format_context_empty(self):
        """Deve lidar com contexto vazio."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = ReminderAgent()
            
            formatted = agent.format_context({})
            
            assert "Sem contexto" in formatted

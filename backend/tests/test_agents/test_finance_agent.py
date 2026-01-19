"""
Testes para FinanceAgent.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import json

from app.ai.agents import FinanceAgent


class TestFinanceAgentInit:
    """Testes de inicialização."""

    def test_agent_initialization(self):
        """Deve inicializar corretamente."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = FinanceAgent()
            
            assert agent.name == "FinanceAgent"
            assert "financeira" in agent.description.lower()

    def test_system_prompt_contains_categories(self):
        """System prompt deve conter categorias."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = FinanceAgent()
            
            prompt = agent.system_prompt
            assert "Alimentação" in prompt
            assert "Transporte" in prompt
            assert "Salário" in prompt


class TestFinanceAgentProcess:
    """Testes de processamento."""

    @pytest.mark.asyncio
    async def test_process_registers_expense(self):
        """Deve registrar despesa."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI') as mock_llm:
            mock_instance = MagicMock()
            
            mock_instance.ainvoke = AsyncMock(side_effect=[
                MagicMock(content=json.dumps({
                    "intent": "register",
                    "sub_intent": "expense"
                })),
                MagicMock(content=json.dumps({
                    "type": "expense",
                    "amount": 50.00,
                    "description": "Almoço",
                    "category": "Alimentação",
                    "transaction_date": "2026-01-14",
                    "is_recurring": False,
                    "tags": ["alimentação"],
                    "confidence": 0.9
                }))
            ])
            mock_llm.return_value = mock_instance
            
            agent = FinanceAgent()
            agent.llm = mock_instance
            
            result = await agent.process(
                message="Gastei 50 reais no almoço",
                context={"timezone": "America/Sao_Paulo"}
            )
            
            assert result["next_action"] == "create_finance"
            assert "finance" in result["entities"]
            assert result["entities"]["finance"]["amount"] == 50.00

    @pytest.mark.asyncio
    async def test_process_handles_query(self):
        """Deve processar consulta."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI') as mock_llm:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(side_effect=[
                MagicMock(content=json.dumps({
                    "intent": "query",
                    "sub_intent": "monthly_summary"
                })),
                MagicMock(content=json.dumps({
                    "query_type": "monthly_summary"
                }))
            ])
            mock_llm.return_value = mock_instance
            
            agent = FinanceAgent()
            agent.llm = mock_instance
            
            result = await agent.process(
                message="Quanto gastei este mês?",
                context={}
            )
            
            assert result["next_action"] == "query_finance"

    @pytest.mark.asyncio
    async def test_process_asks_clarification(self):
        """Deve pedir esclarecimento."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI') as mock_llm:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=MagicMock(
                content=json.dumps({
                    "intent": "clarify"
                })
            ))
            mock_llm.return_value = mock_instance
            
            agent = FinanceAgent()
            agent.llm = mock_instance
            
            result = await agent.process(
                message="dinheiro",
                context={}
            )
            
            assert result["next_action"] == "await_clarification"

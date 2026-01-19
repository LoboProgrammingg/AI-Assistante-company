"""
Testes para MeetingAgent.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import json

from app.ai.agents import MeetingAgent


class TestMeetingAgentInit:
    """Testes de inicialização."""

    def test_agent_initialization(self):
        """Deve inicializar corretamente."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = MeetingAgent()
            
            assert agent.name == "MeetingAgent"
            assert "reuniões" in agent.description.lower()

    def test_system_prompt_contains_responsibilities(self):
        """System prompt deve conter responsabilidades."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = MeetingAgent()
            
            prompt = agent.system_prompt
            assert "resumir" in prompt.lower()
            assert "action items" in prompt.lower()
            assert "participantes" in prompt.lower()


class TestMeetingAgentProcess:
    """Testes de processamento."""

    @pytest.mark.asyncio
    async def test_process_analyzes_meeting(self):
        """Deve analisar reunião."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI') as mock_llm:
            mock_instance = MagicMock()
            mock_instance.ainvoke = AsyncMock(return_value=MagicMock(
                content=json.dumps({
                    "title": "Reunião de Planejamento",
                    "summary": "Discussão sobre próximos passos do projeto X.",
                    "key_topics": [{"topic": "Cronograma", "summary": "Definição de prazos"}],
                    "action_items": [{"task": "Enviar proposta", "responsible": "João"}],
                    "participants": [{"name": "João", "role": "Gerente"}],
                    "decisions": [{"decision": "Aprovar orçamento"}],
                    "keywords": ["projeto", "cronograma"],
                    "sentiment": "positive",
                    "confidence": 0.85
                })
            ))
            mock_llm.return_value = mock_instance
            
            agent = MeetingAgent()
            agent.llm = mock_instance
            
            transcription = """
            João: Vamos começar a reunião. O projeto está progredindo bem.
            Maria: Sim, precisamos definir os próximos passos.
            João: Fica decidido que vamos aprovar o orçamento.
            Maria: Ok, vou enviar a proposta até sexta.
            """ * 5
            
            result = await agent.process(
                message=transcription,
                context={"transcription": transcription}
            )
            
            assert result["next_action"] == "create_meeting"
            assert "meeting" in result["entities"]
            assert result["entities"]["meeting"]["title"] == "Reunião de Planejamento"

    @pytest.mark.asyncio
    async def test_process_short_transcription(self):
        """Deve rejeitar transcrição curta."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = MeetingAgent()
            
            result = await agent.process(
                message="Oi",
                context={}
            )
            
            assert result["next_action"] == "await_clarification"
            assert "curta" in result["response"].lower()


class TestMeetingAgentFormatSummary:
    """Testes de formatação de resumo."""

    def test_format_summary_response_complete(self):
        """Deve formatar resumo completo."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = MeetingAgent()
            
            data = {
                "title": "Sprint Review",
                "summary": "Revisão das entregas da sprint.",
                "key_topics": [{"topic": "Frontend"}, {"topic": "Backend"}],
                "action_items": [{"task": "Corrigir bug", "responsible": "Maria"}],
                "decisions": [{"decision": "Lançar versão 2.0"}]
            }
            
            result = agent._format_summary_response(data)
            
            assert "Sprint Review" in result
            assert "Frontend" in result
            assert "Corrigir bug" in result
            assert "Maria" in result

    def test_format_summary_response_minimal(self):
        """Deve formatar resumo mínimo."""
        with patch('app.ai.agents.base_agent.ChatGoogleGenerativeAI'):
            agent = MeetingAgent()
            
            data = {"title": "Reunião"}
            
            result = agent._format_summary_response(data)
            
            assert "Reunião" in result
            assert "salva com sucesso" in result

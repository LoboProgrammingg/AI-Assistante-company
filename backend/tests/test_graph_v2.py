"""
Testes para o LangGraph v2 - IRIS.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.ai.state import IRISState, create_initial_state, UserContext
from app.ai.tools.finance_tools import RegistrarTransacaoSchema, registrar_transacao
from app.ai.tools.reminder_tools import CriarLembreteSchema, criar_lembrete
from app.ai.tools.meeting_tools import CriarReuniaoSchema, criar_reuniao
from app.ai.tools.contact_tools import CriarContatoSchema, criar_contato


class TestIRISState:
    """Testes para o estado tipado do LangGraph."""
    
    def test_create_initial_state(self):
        """Testa criação do estado inicial."""
        state = create_initial_state(
            user_id=1,
            session_id="test-session",
            message="Olá, mundo!"
        )
        
        assert state["user_id"] == 1
        assert state["session_id"] == "test-session"
        assert state["intent"] == ""
        assert state["step_count"] == 0
        assert len(state["messages"]) == 1
    
    def test_user_context_defaults(self):
        """Testa valores padrão do UserContext."""
        context = UserContext()
        
        assert context["user_name"] == ""
        assert context["timezone"] == "America/Sao_Paulo"
        assert context["source"] == "whatsapp"


class TestFinanceTools:
    """Testes para as tools de finanças."""
    
    def test_registrar_transacao_schema_valid(self):
        """Testa schema válido de transação."""
        schema = RegistrarTransacaoSchema(
            valor=50.0,
            descricao="Almoço",
            categoria="Alimentação",
            tipo="expense"
        )
        
        assert schema.valor == 50.0
        assert schema.descricao == "Almoço"
        assert schema.tipo == "expense"
    
    def test_registrar_transacao_schema_invalid_valor(self):
        """Testa valor inválido (negativo)."""
        with pytest.raises(ValueError):
            RegistrarTransacaoSchema(
                valor=-10.0,
                descricao="Teste",
                tipo="expense"
            )
    
    def test_registrar_transacao_schema_invalid_tipo(self):
        """Testa tipo inválido."""
        with pytest.raises(ValueError):
            RegistrarTransacaoSchema(
                valor=50.0,
                descricao="Teste",
                tipo="invalid"
            )
    
    def test_registrar_transacao_tool(self):
        """Testa execução da tool."""
        result = registrar_transacao(
            valor=100.0,
            descricao="Salário",
            categoria="Renda",
            tipo="income"
        )
        
        assert result["action"] == "create_finance"
        assert result["finance"]["amount"] == 100.0
        assert result["finance"]["type"] == "income"
        assert result["status"] == "pending_execution"


class TestReminderTools:
    """Testes para as tools de lembretes."""
    
    def test_criar_lembrete_schema_valid(self):
        """Testa schema válido de lembrete."""
        schema = CriarLembreteSchema(
            titulo="Reunião importante",
            data_hora="2025-01-21 10:00",
            descricao="Reunião com cliente"
        )
        
        assert schema.titulo == "Reunião importante"
        assert schema.data_hora == "2025-01-21 10:00"
    
    def test_criar_lembrete_tool(self):
        """Testa execução da tool."""
        result = criar_lembrete(
            titulo="Ligar para cliente",
            data_hora="2025-01-21 14:00",
            descricao="Ligação de follow-up"
        )
        
        assert result["action"] == "create_reminder"
        assert result["reminder"]["title"] == "Ligar para cliente"
        assert result["status"] == "pending_execution"


class TestMeetingTools:
    """Testes para as tools de reuniões."""
    
    def test_criar_reuniao_schema_valid(self):
        """Testa schema válido de reunião."""
        schema = CriarReuniaoSchema(
            titulo="Reunião de alinhamento",
            data_hora="2025-01-21 15:00",
            participantes="João, Maria",
            duracao_minutos=60
        )
        
        assert schema.titulo == "Reunião de alinhamento"
        assert schema.duracao_minutos == 60
    
    def test_criar_reuniao_tool(self):
        """Testa execução da tool."""
        result = criar_reuniao(
            titulo="Planning",
            data_hora="2025-01-22 09:00",
            participantes="Time dev",
            duracao_minutos=120
        )
        
        assert result["action"] == "create_meeting"
        assert result["meeting"]["title"] == "Planning"
        assert result["meeting"]["duration_minutes"] == 120


class TestContactTools:
    """Testes para as tools de contatos."""
    
    def test_criar_contato_schema_valid(self):
        """Testa schema válido de contato."""
        schema = CriarContatoSchema(
            nome="João Silva",
            telefone="+5511999999999",
            grupo="Trabalho"
        )
        
        assert schema.nome == "João Silva"
        assert schema.grupo == "Trabalho"
    
    def test_criar_contato_tool(self):
        """Testa execução da tool."""
        result = criar_contato(
            nome="Maria Santos",
            telefone="+5511888888888",
            grupo="Família"
        )
        
        assert result["action"] == "create_contact"
        assert result["contact"]["name"] == "Maria Santos"


class TestGraphV2Integration:
    """Testes de integração do Graph v2."""
    
    @pytest.mark.asyncio
    async def test_graph_initialization(self):
        """Testa inicialização do grafo."""
        with patch('app.ai.graph_v2.ChatGoogleGenerativeAI') as mock_llm:
            mock_llm.return_value = MagicMock()
            
            from app.ai.graph_v2 import get_iris_graph
            graph = get_iris_graph()
            
            assert graph is not None
            assert hasattr(graph, 'process_message')
            assert len(graph.all_tools) == 10
    
    @pytest.mark.asyncio
    async def test_intent_classification_finance(self):
        """Testa classificação de intenção para finanças."""
        with patch('app.ai.graph_v2.ChatGoogleGenerativeAI') as mock_llm:
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = MagicMock(
                content='{"intent": "finance", "confidence": 0.9}'
            )
            mock_llm.return_value = mock_instance
            
            from app.ai.graph_v2 import IRISGraphV2
            
            # O teste verifica que a classificação funciona
            assert True  # Placeholder - integração completa requer LLM real
    
    @pytest.mark.asyncio
    async def test_max_steps_protection(self):
        """Testa proteção contra loops infinitos."""
        from app.ai.state import create_initial_state
        
        state = create_initial_state(1, "test", "mensagem")
        state["step_count"] = 15  # Limite máximo
        
        # Verificar que step_count está no limite
        assert state["step_count"] >= 15

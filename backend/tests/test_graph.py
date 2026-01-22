"""
Testes unitários para o grafo LangGraph IRIS.

Testa:
- Classificação de intenções
- Fluxo de execução de tools
- Estado imutável
- Respostas corretas
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.state import IRISState, create_initial_state
from app.ai.nodes.router import RouterNode
from app.ai.nodes.agents import AgentNodes
from app.ai.nodes.tool_executor import ToolExecutorNode
from app.ai.nodes.error_handler import ErrorHandlerNode


class TestRouterNode:
    """Testes para o RouterNode."""

    @pytest.fixture
    def router_node(self):
        """Cria instância do RouterNode com LLM mockado."""
        mock_llm = MagicMock()
        return RouterNode(mock_llm)

    def test_route_returns_dict(self, router_node):
        """Verifica que route retorna dict (estado imutável)."""
        state = create_initial_state(
            user_id=1,
            session_id="test",
            message="gastei 50 reais no mercado",
        )
        
        with patch("app.ai.nodes.router.get_optimizer") as mock_optimizer:
            mock_optimizer.return_value.should_use_fast_classification.return_value = (True, "finance")
            
            result = router_node.route(state)
            
            assert isinstance(result, dict)
            assert "intent" in result
            assert "confidence" in result
            assert "step_count" in result

    def test_fast_classification_finance(self, router_node):
        """Testa classificação rápida para finanças."""
        state = create_initial_state(
            user_id=1,
            session_id="test",
            message="gastei R$100 no almoço",
        )
        
        with patch("app.ai.nodes.router.get_optimizer") as mock_optimizer:
            mock_optimizer.return_value.should_use_fast_classification.return_value = (True, "finance")
            
            result = router_node.route(state)
            
            assert result["intent"] == "finance"
            assert result["confidence"] == 0.85

    def test_fast_classification_reminder(self, router_node):
        """Testa classificação rápida para lembretes."""
        state = create_initial_state(
            user_id=1,
            session_id="test",
            message="me lembre de ligar para João amanhã às 10h",
        )
        
        with patch("app.ai.nodes.router.get_optimizer") as mock_optimizer:
            mock_optimizer.return_value.should_use_fast_classification.return_value = (True, "reminder")
            
            result = router_node.route(state)
            
            assert result["intent"] == "reminder"

    def test_loop_protection(self, router_node):
        """Testa proteção contra loops infinitos."""
        state = create_initial_state(
            user_id=1,
            session_id="test",
            message="teste",
        )
        state["step_count"] = 20  # Acima do limite
        
        result = router_node.route(state)
        
        assert result["intent"] == "error"
        assert "error" in result

    def test_route_by_intent(self):
        """Testa roteamento por intenção."""
        state = {"intent": "finance", "error": None}
        assert RouterNode.route_by_intent(state) == "finance"
        
        state = {"intent": "reminder", "error": None}
        assert RouterNode.route_by_intent(state) == "reminder"
        
        state = {"intent": "general", "error": "algo errado"}
        assert RouterNode.route_by_intent(state) == "error"

    def test_should_execute_tools(self):
        """Testa decisão de executar tools."""
        state = {"tool_calls": [{"name": "test"}], "error": None}
        assert RouterNode.should_execute_tools(state) == "execute"
        
        state = {"tool_calls": [], "error": None}
        assert RouterNode.should_execute_tools(state) == "respond"
        
        state = {"tool_calls": [], "error": "algo"}
        assert RouterNode.should_execute_tools(state) == "error"


class TestAgentNodes:
    """Testes para os AgentNodes."""

    @pytest.fixture
    def agent_nodes(self):
        """Cria instância do AgentNodes com LLM mockado."""
        mock_llm = MagicMock()
        return AgentNodes(mock_llm)

    def test_finance_agent_returns_dict(self, agent_nodes):
        """Verifica que finance_agent retorna dict."""
        state = create_initial_state(
            user_id=1,
            session_id="test",
            message="gastei 50 reais",
        )
        
        mock_response = MagicMock()
        mock_response.tool_calls = [{"name": "registrar_transacao", "args": {}}]
        agent_nodes.llm_with_tools.invoke.return_value = mock_response
        
        result = agent_nodes.finance_agent(state)
        
        assert isinstance(result, dict)
        assert "tool_calls" in result

    def test_agent_without_tool_calls(self, agent_nodes):
        """Testa quando LLM responde sem chamar tools."""
        state = create_initial_state(
            user_id=1,
            session_id="test",
            message="olá",
        )
        
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "Olá! Como posso ajudar?"
        agent_nodes.llm_with_tools.invoke.return_value = mock_response
        
        result = agent_nodes.finance_agent(state)
        
        assert isinstance(result, dict)
        assert "messages" in result


class TestToolExecutorNode:
    """Testes para o ToolExecutorNode."""

    @pytest.fixture
    def tool_executor(self):
        """Cria instância do ToolExecutorNode com tools mockadas."""
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.invoke.return_value = {"success": True}
        return ToolExecutorNode([mock_tool])

    def test_execute_returns_dict(self, tool_executor):
        """Verifica que execute retorna dict."""
        state = {
            "tool_calls": [{"name": "test_tool", "args": {}}],
        }
        
        result = tool_executor.execute(state)
        
        assert isinstance(result, dict)
        assert "tool_results" in result
        assert "tool_calls" in result
        assert result["tool_calls"] == []  # Limpo após execução

    def test_execute_tool_success(self, tool_executor):
        """Testa execução bem-sucedida de tool."""
        state = {
            "tool_calls": [{"name": "test_tool", "args": {"valor": 100}}],
        }
        
        result = tool_executor.execute(state)
        
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["success"] is True

    def test_execute_tool_not_found(self, tool_executor):
        """Testa quando tool não é encontrada."""
        state = {
            "tool_calls": [{"name": "tool_inexistente", "args": {}}],
        }
        
        result = tool_executor.execute(state)
        
        assert result["tool_results"][0]["success"] is False
        assert "não encontrada" in result["tool_results"][0]["error"]


class TestErrorHandlerNode:
    """Testes para o ErrorHandlerNode."""

    def test_handle_returns_dict(self):
        """Verifica que handle retorna dict."""
        state = {"error": "Teste de erro", "messages": []}
        
        result = ErrorHandlerNode.handle(state)
        
        assert isinstance(result, dict)
        assert "messages" in result
        assert len(result["messages"]) == 1

    def test_handle_error_message(self):
        """Verifica mensagem de erro amigável."""
        state = {"error": "Erro interno", "messages": []}
        
        result = ErrorHandlerNode.handle(state)
        
        message_content = result["messages"][0].content
        assert "Desculpe" in message_content
        assert "erro" in message_content.lower()


class TestCreateInitialState:
    """Testes para criação de estado inicial."""

    def test_create_initial_state_basic(self):
        """Testa criação básica de estado."""
        state = create_initial_state(
            user_id=123,
            session_id="abc",
            message="teste",
        )
        
        assert state["user_id"] == 123
        assert state["session_id"] == "abc"
        assert len(state["messages"]) == 1
        assert state["messages"][0].content == "teste"

    def test_create_initial_state_with_context(self):
        """Testa criação com contexto."""
        state = create_initial_state(
            user_id=123,
            session_id="abc",
            message="teste",
            context={
                "user_name": "João",
                "timezone": "America/Cuiaba",
            },
        )
        
        assert state["user_context"].user_name == "João"
        assert state["user_context"].timezone == "America/Cuiaba"


@pytest.mark.asyncio
class TestGraphIntegration:
    """Testes de integração do grafo completo."""

    @pytest.fixture
    def mock_graph(self):
        """Cria grafo com componentes mockados."""
        with patch("app.ai.graph_v2.ChatGoogleGenerativeAI"):
            from app.ai.graph_v2 import IRISGraphV2
            return IRISGraphV2()

    async def test_process_message_returns_dict(self, mock_graph):
        """Verifica que process_message retorna dict com campos esperados."""
        with patch.object(mock_graph.graph, "ainvoke") as mock_invoke:
            mock_invoke.return_value = {
                "messages": [MagicMock(content="Resposta teste")],
                "intent": "general",
                "entities": {},
                "confidence": 0.9,
            }
            
            result = await mock_graph.process_message(
                user_id=1,
                session_id="test",
                message="olá",
            )
            
            assert "response" in result
            assert "intent" in result
            assert "entities" in result
            assert "confidence" in result

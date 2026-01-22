"""
Nós do grafo LangGraph IRIS v2.

Este módulo contém todos os nós separados para melhor organização:
- router: Classificação e roteamento de intenções
- agents: Agentes especializados (finance, reminder, meeting, contact)
- tool_executor: Execução de tools
- general_chat: Chat geral com integrações
- response_formatter: Formatação de respostas
- error_handler: Tratamento de erros
"""

from app.ai.nodes.router import RouterNode
from app.ai.nodes.agents import AgentNodes
from app.ai.nodes.tool_executor import ToolExecutorNode
from app.ai.nodes.general_chat import GeneralChatNode
from app.ai.nodes.response_formatter import ResponseFormatterNode
from app.ai.nodes.error_handler import ErrorHandlerNode

__all__ = [
    "RouterNode",
    "AgentNodes",
    "ToolExecutorNode",
    "GeneralChatNode",
    "ResponseFormatterNode",
    "ErrorHandlerNode",
]

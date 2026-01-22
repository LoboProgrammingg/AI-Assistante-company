"""
Tool Executor Node - Execução de tools.

Responsável por:
- Executar as tools chamadas pelo LLM
- Coletar resultados e erros
- Separação clara: LLM decide, este nó executa
"""

import logging
from typing import TYPE_CHECKING, List

from app.ai.state import IRISState

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class ToolExecutorNode:
    """Nó responsável pela execução de tools."""

    def __init__(self, tools: List["BaseTool"]):
        """
        Args:
            tools: Lista de todas as tools disponíveis
        """
        self.tools = tools
        self._tools_by_name = {tool.name: tool for tool in tools}

    def execute(self, state: IRISState) -> dict:
        """
        Executa as tools chamadas pelo LLM.
        
        IMPORTANTE: Retorna dict com atualizações (estado imutável - padrão LangGraph)
        """
        tool_calls = state.get("tool_calls", [])
        tool_results = []

        for tc in tool_calls:
            tool_name = tc.get("name", "")
            tool_args = tc.get("args", {})

            try:
                # Encontrar e executar a tool
                tool = self._tools_by_name.get(tool_name)
                if tool:
                    result = tool.invoke(tool_args)
                    tool_results.append({
                        "tool": tool_name,
                        "result": result,
                        "success": True,
                    })
                else:
                    logger.warning(f"Tool não encontrada: {tool_name}")
                    tool_results.append({
                        "tool": tool_name,
                        "error": f"Tool '{tool_name}' não encontrada",
                        "success": False,
                    })
            except Exception as e:
                logger.error(f"Erro ao executar tool {tool_name}: {e}")
                tool_results.append({
                    "tool": tool_name,
                    "error": str(e),
                    "success": False,
                })

        # Retornar dict imutável
        return {
            "tool_results": tool_results,
            "tool_calls": [],  # Limpar após execução
        }

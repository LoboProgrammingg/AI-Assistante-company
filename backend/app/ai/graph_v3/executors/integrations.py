"""
Integrations Executor - Pesquisas e APIs externas.

Ações que retornam dados para o LLM processar.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

logger = logging.getLogger(__name__)


class IntegrationsExecutor:
    """Executor de pesquisas e integrações externas."""

    @staticmethod
    def web_search(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Pesquisa na web - retorna para LLM processar."""
        return ExecutionResult(
            success=True,
            action_type="web_search",
            data={"query": params.get("query", ""), "needs_llm": True},
            response_template=None,
        )

    @staticmethod
    def search_news(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Busca notícias - retorna para LLM processar."""
        return ExecutionResult(
            success=True,
            action_type="search_news",
            data={"query": params.get("query", ""), "needs_llm": True},
            response_template=None,
        )

    @staticmethod
    def get_weather(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Consulta clima."""
        return ExecutionResult(
            success=True,
            action_type="get_weather",
            data={"city": params.get("city", params.get("cidade", "")), "needs_llm": True},
            response_template=None,
        )

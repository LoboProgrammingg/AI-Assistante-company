"""
Integrations Executor - Pesquisas e APIs externas.

Ações que retornam dados para o LLM processar.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult
from app.config import settings

logger = logging.getLogger(__name__)


class IntegrationsExecutor:
    """Executor de pesquisas e integrações externas."""

    @staticmethod
    def web_search(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Pesquisa na web usando Tavily API."""
        query = params.get("query", params.get("original_message", ""))
        
        logger.info(f"[WEB_SEARCH] 🔍 Iniciando busca: '{query}'")
        
        if not query:
            logger.warning("[WEB_SEARCH] ⚠️ Query vazia")
            return ExecutionResult(
                success=False,
                action_type="web_search",
                error="Nenhuma query fornecida para busca",
            )
        
        try:
            from tavily import TavilyClient
            
            api_key = settings.TAVILY_API_KEY
            logger.info(f"[WEB_SEARCH] API Key configurada: {bool(api_key)} (len={len(api_key) if api_key else 0})")
            
            if not api_key:
                logger.error("[WEB_SEARCH] ❌ TAVILY_API_KEY não configurada no Railway!")
                return ExecutionResult(
                    success=True,
                    action_type="web_search",
                    data={
                        "query": query,
                        "answer": "⚠️ Busca web não disponível. Configure TAVILY_API_KEY no Railway.",
                        "results": [],
                        "message": "Busca web não disponível no momento",
                    },
                )
            
            client = TavilyClient(api_key=api_key)
            
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_answer=True,
            )
            
            results = []
            for r in response.get("results", [])[:5]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:500],
                })
            
            answer = response.get("answer", "")
            
            logger.info(f"[WEB_SEARCH] Query: {query} | Results: {len(results)}")
            
            return ExecutionResult(
                success=True,
                action_type="web_search",
                data={
                    "query": query,
                    "answer": answer,
                    "results": results,
                    "needs_llm": True,
                },
            )
            
        except ImportError:
            logger.error("[WEB_SEARCH] Tavily não instalado")
            return ExecutionResult(
                success=True,
                action_type="web_search",
                data={"query": query, "results": [], "message": "Módulo de busca não disponível"},
            )
        except Exception as e:
            logger.error(f"[WEB_SEARCH] Erro: {e}")
            return ExecutionResult(
                success=False,
                action_type="web_search",
                error=str(e),
            )

    @staticmethod
    def search_news(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Busca notícias usando Tavily API."""
        query = params.get("query", params.get("original_message", ""))
        
        try:
            from tavily import TavilyClient
            
            api_key = settings.TAVILY_API_KEY
            if not api_key:
                return ExecutionResult(
                    success=True,
                    action_type="search_news",
                    data={"query": query, "results": [], "message": "Busca não disponível"},
                )
            
            client = TavilyClient(api_key=api_key)
            
            response = client.search(
                query=f"notícias {query}",
                search_depth="basic",
                max_results=5,
                include_answer=True,
            )
            
            results = []
            for r in response.get("results", [])[:5]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:300],
                })
            
            return ExecutionResult(
                success=True,
                action_type="search_news",
                data={
                    "query": query,
                    "answer": response.get("answer", ""),
                    "results": results,
                    "needs_llm": True,
                },
            )
            
        except Exception as e:
            logger.error(f"[SEARCH_NEWS] Erro: {e}")
            return ExecutionResult(
                success=True,
                action_type="search_news",
                data={"query": query, "results": [], "error": str(e)},
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

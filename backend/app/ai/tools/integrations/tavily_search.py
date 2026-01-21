"""
Tavily Web Search - Busca na web em tempo real.
Docs: https://docs.tavily.com/
"""

import logging
from typing import Optional
from langchain_core.tools import tool
from tavily import TavilyClient
from app.config import settings

logger = logging.getLogger(__name__)


class TavilySearchTools:
    """Tools para busca na web usando Tavily."""

    def __init__(self):
        self.client = TavilyClient(api_key=settings.TAVILY_API_KEY) if settings.TAVILY_API_KEY else None

    @property
    def is_configured(self) -> bool:
        return bool(settings.TAVILY_API_KEY)

    def get_tools(self) -> list:
        if not self.is_configured:
            logger.warning("[TAVILY] API key não configurada")
            return []
        return [self._search_web, self._search_news]

    @tool
    def _search_web(query: str, max_results: int = 5) -> str:
        """
        Busca informações na web em tempo real.
        Use para: notícias, informações atualizadas, pesquisas gerais.
        
        Args:
            query: Termo de busca
            max_results: Número máximo de resultados (1-10)
        """
        try:
            client = TavilyClient(api_key=settings.TAVILY_API_KEY)
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=min(max_results, 10),
                include_answer=True,
            )
            
            results = []
            if response.get("answer"):
                results.append(f"Resumo: {response['answer']}")
            
            for r in response.get("results", [])[:max_results]:
                results.append(f"- {r['title']}: {r['content'][:200]}...")
            
            return "\n".join(results) if results else "Nenhum resultado encontrado."
        except Exception as e:
            logger.error(f"[TAVILY] Erro na busca: {e}")
            return f"Erro na busca: {str(e)}"

    @tool
    def _search_news(query: str, days: int = 7) -> str:
        """
        Busca notícias recentes sobre um tema.
        
        Args:
            query: Termo de busca
            days: Notícias dos últimos N dias (1-30)
        """
        try:
            client = TavilyClient(api_key=settings.TAVILY_API_KEY)
            response = client.search(
                query=query,
                search_depth="basic",
                topic="news",
                days=min(days, 30),
                max_results=5,
                include_answer=True,
            )
            
            results = []
            if response.get("answer"):
                results.append(f"Resumo: {response['answer']}")
            
            for r in response.get("results", []):
                results.append(f"- {r['title']}: {r['content'][:150]}...")
            
            return "\n".join(results) if results else "Nenhuma notícia encontrada."
        except Exception as e:
            logger.error(f"[TAVILY] Erro ao buscar notícias: {e}")
            return f"Erro: {str(e)}"


tavily_tools = TavilySearchTools()

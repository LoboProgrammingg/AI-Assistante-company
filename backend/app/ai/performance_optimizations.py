"""
Otimizações de performance para a IA IRIS.

Este módulo contém melhorias de performance implementadas.
"""

import hashlib
import logging
from functools import lru_cache
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class QueryCache:
    """
    Cache em memória para queries frequentes.
    Evita chamadas repetidas ao banco de dados.
    """

    _instance = None
    _cache: Dict[str, Any] = {}
    _max_size = 100

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._cache = {}
        return cls._instance

    @staticmethod
    def _make_key(prefix: str, *args, **kwargs) -> str:
        """Gera chave única para o cache."""
        key_parts = [prefix] + [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
        return hashlib.md5(":".join(key_parts).encode()).hexdigest()

    def get(self, prefix: str, *args, **kwargs) -> Optional[Any]:
        """Busca valor no cache."""
        key = self._make_key(prefix, *args, **kwargs)
        return self._cache.get(key)

    def set(self, value: Any, prefix: str, *args, **kwargs) -> None:
        """Define valor no cache."""
        if len(self._cache) >= self._max_size:
            # Remove 10% dos itens mais antigos
            keys_to_remove = list(self._cache.keys())[: self._max_size // 10]
            for k in keys_to_remove:
                del self._cache[k]

        key = self._make_key(prefix, *args, **kwargs)
        self._cache[key] = value

    def invalidate(self, prefix: str = None) -> None:
        """Invalida cache por prefixo ou todo."""
        if prefix is None:
            self._cache.clear()
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._cache[k]


# Singleton global
query_cache = QueryCache()


class ContextOptimizer:
    """
    Otimiza o contexto enviado para a IA.
    Reduz tokens desnecessários.
    """

    MAX_CONTEXT_CHARS = 8000  # Limite de caracteres no contexto
    MAX_HISTORY_MESSAGES = 10  # Máximo de mensagens no histórico

    @staticmethod
    def optimize_context_prompt(context_prompt: str) -> str:
        """
        Otimiza o prompt de contexto para reduzir tokens.
        """
        if len(context_prompt) <= ContextOptimizer.MAX_CONTEXT_CHARS:
            return context_prompt

        # Truncar mantendo início e fim
        half = ContextOptimizer.MAX_CONTEXT_CHARS // 2
        optimized = context_prompt[:half] + "\n...[CONTEXTO TRUNCADO]...\n" + context_prompt[-half:]
        logger.debug(f"[PERF] Contexto truncado de {len(context_prompt)} para {len(optimized)} chars")
        return optimized

    @staticmethod
    def optimize_conversation_history(messages: list, max_messages: int = None) -> list:
        """
        Otimiza histórico de conversa mantendo apenas mensagens relevantes.
        """
        max_msgs = max_messages or ContextOptimizer.MAX_HISTORY_MESSAGES

        if len(messages) <= max_msgs:
            return messages

        # Manter primeiras 2 e últimas N-2 mensagens
        return messages[:2] + messages[-(max_msgs - 2) :]


class ResponseOptimizer:
    """
    Otimiza respostas da IA.
    """

    @staticmethod
    def should_use_streaming(message: str) -> bool:
        """
        Determina se deve usar streaming para a resposta.
        Respostas longas se beneficiam de streaming.
        """
        # Perguntas complexas geralmente geram respostas longas
        complex_keywords = ["explique", "como", "por que", "análise", "resumo", "compare"]
        return any(kw in message.lower() for kw in complex_keywords)


# Métricas de performance (para monitoramento)
class PerformanceMetrics:
    """Coleta métricas de performance."""

    _metrics: Dict[str, list] = {}

    @classmethod
    def track(cls, metric_name: str, value: float) -> None:
        """Registra uma métrica."""
        if metric_name not in cls._metrics:
            cls._metrics[metric_name] = []

        cls._metrics[metric_name].append(value)

        # Manter apenas últimas 100 medições
        if len(cls._metrics[metric_name]) > 100:
            cls._metrics[metric_name] = cls._metrics[metric_name][-100:]

    @classmethod
    def get_average(cls, metric_name: str) -> float:
        """Retorna média de uma métrica."""
        values = cls._metrics.get(metric_name, [])
        return sum(values) / len(values) if values else 0.0

    @classmethod
    def get_summary(cls) -> Dict[str, float]:
        """Retorna resumo de todas as métricas."""
        return {name: cls.get_average(name) for name in cls._metrics}

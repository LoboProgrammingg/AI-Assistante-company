"""
LLM Module - Utilitários para chamadas LLM.

Componentes:
- LLMRetry: Sistema de retry com backoff exponencial
- invoke_llm_with_retry: Helper para invocar LLM com retry
"""

from app.ai.llm.retry import (
    LLMRetry,
    RetryConfig,
    RetryStats,
    get_retry_stats,
    invoke_llm_with_retry,
    ainvoke_llm_with_retry,
    with_retry,
)

__all__ = [
    "LLMRetry",
    "RetryConfig",
    "RetryStats",
    "get_retry_stats",
    "invoke_llm_with_retry",
    "ainvoke_llm_with_retry",
    "with_retry",
]

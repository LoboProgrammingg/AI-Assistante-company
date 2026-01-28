"""
LLM Retry - Sistema de retry com backoff exponencial para chamadas LLM.

Features:
- Retry automático com backoff exponencial
- Jitter para evitar thundering herd
- Diferentes estratégias por tipo de erro
- Logging estruturado
- Métricas de retry
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional, Type, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuração de retry."""
    
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_range: Tuple[float, float] = (0.5, 1.5)
    
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        Exception,
    )
    
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (
        KeyboardInterrupt,
        SystemExit,
        ValueError,
        TypeError,
    )


@dataclass
class RetryStats:
    """Estatísticas de retry."""
    
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_retries: int = 0
    total_delay_seconds: float = 0.0
    
    def record_success(self, attempts: int, total_delay: float) -> None:
        self.total_calls += 1
        self.successful_calls += 1
        self.total_retries += (attempts - 1)
        self.total_delay_seconds += total_delay
    
    def record_failure(self, attempts: int, total_delay: float) -> None:
        self.total_calls += 1
        self.failed_calls += 1
        self.total_retries += (attempts - 1)
        self.total_delay_seconds += total_delay
    
    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "total_retries": self.total_retries,
            "success_rate": f"{(self.successful_calls / self.total_calls * 100):.1f}%" if self.total_calls > 0 else "N/A",
            "avg_delay_per_call": f"{(self.total_delay_seconds / self.total_calls):.2f}s" if self.total_calls > 0 else "N/A",
        }


_global_stats = RetryStats()


def get_retry_stats() -> RetryStats:
    """Retorna estatísticas globais de retry."""
    return _global_stats


class LLMRetry:
    """
    Gerenciador de retry para chamadas LLM.
    
    Implementa retry com backoff exponencial e jitter.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._stats = _global_stats
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calcula delay com backoff exponencial e jitter."""
        delay = min(
            self.config.base_delay * (self.config.exponential_base ** (attempt - 1)),
            self.config.max_delay
        )
        
        if self.config.jitter:
            jitter_min, jitter_max = self.config.jitter_range
            delay *= random.uniform(jitter_min, jitter_max)
        
        return delay
    
    def _is_retryable(self, exception: Exception) -> bool:
        """Verifica se exceção permite retry."""
        if isinstance(exception, self.config.non_retryable_exceptions):
            return False
        
        return isinstance(exception, self.config.retryable_exceptions)
    
    def _should_retry_on_content(self, result: Any) -> bool:
        """Verifica se deve fazer retry baseado no conteúdo da resposta."""
        if result is None:
            return True
        
        if hasattr(result, 'content') and not result.content:
            return True
        
        return False
    
    def invoke_with_retry(
        self,
        func: Callable,
        *args,
        operation_name: str = "LLM",
        **kwargs
    ) -> Any:
        """
        Executa função com retry.
        
        Args:
            func: Função a executar (ex: llm.invoke)
            *args: Argumentos posicionais
            operation_name: Nome da operação para logs
            **kwargs: Argumentos nomeados
            
        Returns:
            Resultado da função
            
        Raises:
            Exception: Último erro se todos os retries falharem
        """
        last_exception = None
        total_delay = 0.0
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = func(*args, **kwargs)
                
                if self._should_retry_on_content(result) and attempt < self.config.max_attempts:
                    logger.warning(f"[{operation_name}] Resposta vazia, tentando novamente...")
                    delay = self._calculate_delay(attempt)
                    total_delay += delay
                    time.sleep(delay)
                    continue
                
                if attempt > 1:
                    logger.info(f"[{operation_name}] ✓ Sucesso após {attempt} tentativas")
                
                self._stats.record_success(attempt, total_delay)
                return result
                
            except Exception as e:
                last_exception = e
                
                if not self._is_retryable(e):
                    logger.error(f"[{operation_name}] ✗ Erro não-retryable: {type(e).__name__}: {e}")
                    self._stats.record_failure(attempt, total_delay)
                    raise
                
                if attempt >= self.config.max_attempts:
                    logger.error(f"[{operation_name}] ✗ Falha após {attempt} tentativas: {e}")
                    self._stats.record_failure(attempt, total_delay)
                    raise
                
                delay = self._calculate_delay(attempt)
                total_delay += delay
                
                logger.warning(
                    f"[{operation_name}] ⚠ Tentativa {attempt}/{self.config.max_attempts} falhou: "
                    f"{type(e).__name__}. Retry em {delay:.1f}s..."
                )
                
                time.sleep(delay)
        
        self._stats.record_failure(self.config.max_attempts, total_delay)
        raise last_exception
    
    async def ainvoke_with_retry(
        self,
        func: Callable,
        *args,
        operation_name: str = "LLM",
        **kwargs
    ) -> Any:
        """
        Versão async do invoke_with_retry.
        
        Args:
            func: Função async a executar
            *args: Argumentos posicionais
            operation_name: Nome da operação para logs
            **kwargs: Argumentos nomeados
            
        Returns:
            Resultado da função
        """
        last_exception = None
        total_delay = 0.0
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = await func(*args, **kwargs)
                
                if self._should_retry_on_content(result) and attempt < self.config.max_attempts:
                    logger.warning(f"[{operation_name}] Resposta vazia, tentando novamente...")
                    delay = self._calculate_delay(attempt)
                    total_delay += delay
                    await asyncio.sleep(delay)
                    continue
                
                if attempt > 1:
                    logger.info(f"[{operation_name}] ✓ Sucesso após {attempt} tentativas")
                
                self._stats.record_success(attempt, total_delay)
                return result
                
            except Exception as e:
                last_exception = e
                
                if not self._is_retryable(e):
                    logger.error(f"[{operation_name}] ✗ Erro não-retryable: {type(e).__name__}: {e}")
                    self._stats.record_failure(attempt, total_delay)
                    raise
                
                if attempt >= self.config.max_attempts:
                    logger.error(f"[{operation_name}] ✗ Falha após {attempt} tentativas: {e}")
                    self._stats.record_failure(attempt, total_delay)
                    raise
                
                delay = self._calculate_delay(attempt)
                total_delay += delay
                
                logger.warning(
                    f"[{operation_name}] ⚠ Tentativa {attempt}/{self.config.max_attempts} falhou: "
                    f"{type(e).__name__}. Retry em {delay:.1f}s..."
                )
                
                await asyncio.sleep(delay)
        
        self._stats.record_failure(self.config.max_attempts, total_delay)
        raise last_exception


_default_retry = LLMRetry()


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    operation_name: str = "LLM"
):
    """
    Decorator para adicionar retry a funções.
    
    Args:
        max_attempts: Número máximo de tentativas
        base_delay: Delay base entre tentativas
        operation_name: Nome da operação para logs
    """
    config = RetryConfig(max_attempts=max_attempts, base_delay=base_delay)
    retry_manager = LLMRetry(config)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return retry_manager.invoke_with_retry(
                func, *args, operation_name=operation_name, **kwargs
            )
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await retry_manager.ainvoke_with_retry(
                func, *args, operation_name=operation_name, **kwargs
            )
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def invoke_llm_with_retry(
    llm,
    prompt: str,
    operation_name: str = "LLM",
    max_attempts: int = 3
) -> Any:
    """
    Helper para invocar LLM com retry.
    
    Args:
        llm: Instância do LLM (ex: ChatGoogleGenerativeAI)
        prompt: Prompt a enviar
        operation_name: Nome da operação para logs
        max_attempts: Máximo de tentativas
        
    Returns:
        Resposta do LLM
    """
    config = RetryConfig(max_attempts=max_attempts)
    retry = LLMRetry(config)
    
    return retry.invoke_with_retry(
        llm.invoke,
        prompt,
        operation_name=operation_name
    )


async def ainvoke_llm_with_retry(
    llm,
    prompt: str,
    operation_name: str = "LLM",
    max_attempts: int = 3
) -> Any:
    """
    Helper async para invocar LLM com retry.
    
    Args:
        llm: Instância do LLM
        prompt: Prompt a enviar
        operation_name: Nome da operação para logs
        max_attempts: Máximo de tentativas
        
    Returns:
        Resposta do LLM
    """
    config = RetryConfig(max_attempts=max_attempts)
    retry = LLMRetry(config)
    
    return await retry.ainvoke_with_retry(
        llm.ainvoke,
        prompt,
        operation_name=operation_name
    )

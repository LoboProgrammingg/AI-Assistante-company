"""
Logging Seguro - Proteção de dados sensíveis nos logs.

Mascara automaticamente:
- Senhas
- Tokens JWT
- Números de cartão
- CPF/CNPJ
- Emails (parcialmente)
- Telefones
"""

import logging
import re
from typing import Any, Dict

from app.core.security import mask_sensitive_data


class SecureFormatter(logging.Formatter):
    """
    Formatter que mascara dados sensíveis automaticamente.
    
    Uso:
        handler = logging.StreamHandler()
        handler.setFormatter(SecureFormatter())
        logger.addHandler(handler)
    """

    # Padrões para mascarar
    PATTERNS = [
        # JWT tokens
        (r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*', '[JWT_TOKEN]'),
        # Bearer tokens
        (r'Bearer\s+[a-zA-Z0-9_-]+', 'Bearer [TOKEN]'),
        # Senhas em JSON
        (r'"password"\s*:\s*"[^"]*"', '"password": "[REDACTED]"'),
        (r'"current_password"\s*:\s*"[^"]*"', '"current_password": "[REDACTED]"'),
        (r'"new_password"\s*:\s*"[^"]*"', '"new_password": "[REDACTED]"'),
        # API keys
        (r'api[_-]?key["\s:=]+[a-zA-Z0-9_-]{20,}', 'api_key=[REDACTED]'),
        (r'secret[_-]?key["\s:=]+[a-zA-Z0-9_-]{20,}', 'secret_key=[REDACTED]'),
        # Números de cartão (simplificado)
        (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD_NUMBER]'),
        # CPF
        (r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', '[CPF]'),
        (r'\b\d{11}\b(?=.*cpf)', '[CPF]'),
        # CNPJ
        (r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b', '[CNPJ]'),
    ]

    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self._compiled_patterns = [(re.compile(p, re.IGNORECASE), r) for p, r in self.PATTERNS]

    def format(self, record: logging.LogRecord) -> str:
        """Formata log mascarando dados sensíveis."""
        message = super().format(record)
        
        for pattern, replacement in self._compiled_patterns:
            message = pattern.sub(replacement, message)
        
        return message


class SecureLogger:
    """
    Wrapper para logger com proteção automática de dados sensíveis.
    
    Uso:
        logger = SecureLogger(__name__)
        logger.info("User logged in", extra={"email": "user@email.com"})
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _mask_args(self, args: tuple) -> tuple:
        """Mascara argumentos do log."""
        return tuple(
            mask_sensitive_data(str(arg)) if isinstance(arg, str) else arg
            for arg in args
        )

    def _mask_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Mascara kwargs do log."""
        if 'extra' in kwargs and isinstance(kwargs['extra'], dict):
            kwargs['extra'] = {
                k: mask_sensitive_data(str(v)) if isinstance(v, str) else v
                for k, v in kwargs['extra'].items()
            }
        return kwargs

    def debug(self, msg: str, *args, **kwargs):
        self._logger.debug(msg, *self._mask_args(args), **self._mask_kwargs(kwargs))

    def info(self, msg: str, *args, **kwargs):
        self._logger.info(msg, *self._mask_args(args), **self._mask_kwargs(kwargs))

    def warning(self, msg: str, *args, **kwargs):
        self._logger.warning(msg, *self._mask_args(args), **self._mask_kwargs(kwargs))

    def error(self, msg: str, *args, **kwargs):
        self._logger.error(msg, *self._mask_args(args), **self._mask_kwargs(kwargs))

    def critical(self, msg: str, *args, **kwargs):
        self._logger.critical(msg, *self._mask_args(args), **self._mask_kwargs(kwargs))

    def exception(self, msg: str, *args, **kwargs):
        self._logger.exception(msg, *self._mask_args(args), **self._mask_kwargs(kwargs))


def setup_secure_logging():
    """
    Configura logging seguro para toda a aplicação.
    
    Uso no main.py:
        from app.core.secure_logging import setup_secure_logging
        setup_secure_logging()
    """
    # Formato padrão
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Criar handler com formatter seguro
    handler = logging.StreamHandler()
    handler.setFormatter(SecureFormatter(log_format))
    
    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.handlers = []  # Limpar handlers existentes
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def get_secure_logger(name: str) -> SecureLogger:
    """Retorna um logger seguro para o módulo."""
    return SecureLogger(name)

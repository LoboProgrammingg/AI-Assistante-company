"""
Middleware de Sanitização Global.

Aplica sanitização automática em todas as requisições POST/PUT/PATCH.
Protege contra:
- XSS (Cross-Site Scripting)
- SQL Injection
- Command Injection
- Template Injection
"""

import json
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.input_sanitizer import get_sanitizer

logger = logging.getLogger(__name__)


class SanitizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware que sanitiza automaticamente o body de requisições.
    
    Aplica em:
    - POST, PUT, PATCH requests
    - Content-Type: application/json
    
    Exclui:
    - Uploads de arquivos (multipart/form-data)
    - Webhooks externos
    """

    EXCLUDED_PATHS = [
        "/api/v1/webhook",
        "/api/v1/documents/upload",
        "/api/v1/audio",
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Apenas sanitizar métodos que enviam dados
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        # Verificar paths excluídos
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)

        # Verificar content-type
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            return await call_next(request)

        try:
            # Ler e sanitizar body
            body = await request.body()
            if body:
                sanitized_body = await self._sanitize_body(body)
                
                # Substituir request com body sanitizado
                request._body = sanitized_body

        except Exception as e:
            logger.warning(f"[SANITIZER] Erro ao sanitizar request: {e}")
            # Continuar com body original em caso de erro

        return await call_next(request)

    async def _sanitize_body(self, body: bytes) -> bytes:
        """Sanitiza o body JSON."""
        try:
            data = json.loads(body.decode("utf-8"))
            sanitizer = get_sanitizer()
            
            if isinstance(data, dict):
                sanitized_data = self._sanitize_dict(data, sanitizer)
            elif isinstance(data, list):
                sanitized_data = [
                    self._sanitize_dict(item, sanitizer) if isinstance(item, dict) else item
                    for item in data
                ]
            else:
                sanitized_data = data

            return json.dumps(sanitized_data).encode("utf-8")

        except json.JSONDecodeError:
            return body

    def _sanitize_dict(self, data: dict, sanitizer) -> dict:
        """Sanitiza dicionário recursivamente."""
        sanitized = {}
        
        for key, value in data.items():
            # Campos sensíveis que NÃO devem ser sanitizados (senhas, tokens)
            if key in ("password", "password_confirm", "current_password", "new_password", "token"):
                sanitized[key] = value
            elif isinstance(value, str):
                # Sanitizar strings
                if key in ("message", "content", "text", "description", "notes"):
                    sanitized[key] = sanitizer.sanitize_message(value)
                else:
                    sanitized[key] = sanitizer.sanitize_field(value, key)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value, sanitizer)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_dict(item, sanitizer) if isinstance(item, dict)
                    else sanitizer.sanitize_field(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

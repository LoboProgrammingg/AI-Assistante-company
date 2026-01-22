"""
Middleware de Segurança para FastAPI.
Adiciona headers de segurança e validação de requisições.
"""

import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.core.security import RequestValidator, SecurityConfig

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware que adiciona headers de segurança em todas as respostas.

    Headers incluídos:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security
    - Content-Security-Policy
    - Referrer-Policy
    
    SEGURANÇA: Usa CSP diferente para dev/prod
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Usar headers apropriados para o ambiente
        headers = (
            SecurityConfig.SECURITY_HEADERS_DEV 
            if settings.DEBUG 
            else SecurityConfig.SECURITY_HEADERS
        )

        # Adicionar headers de segurança
        for header, value in headers.items():
            # Não sobrescrever CSP em respostas de API (pode quebrar frontend)
            if header == "Content-Security-Policy" and request.url.path.startswith("/api"):
                continue
            response.headers[header] = value

        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware que valida requisições por padrões suspeitos.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Validar requisição
        is_valid, error = RequestValidator.validate_request(request)

        if not is_valid:
            logger.warning(f"Requisição bloqueada: {error} - IP: {RequestValidator.get_client_ip(request)}")
            return Response(content='{"error": "Request blocked"}', status_code=403, media_type="application/json")

        return await call_next(request)


def add_security_middlewares(app: ASGIApp) -> None:
    """Adiciona todos os middlewares de segurança ao app."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestValidationMiddleware)

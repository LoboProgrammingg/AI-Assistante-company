"""
Exceções customizadas e handlers centralizados.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Exceção base da aplicação."""

    def __init__(
        self,
        message: str,
        code: str = "app_error",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    """Recurso não encontrado."""

    def __init__(self, resource: str, resource_id: Any = None):
        message = f"{resource} não encontrado"
        if resource_id:
            message = f"{resource} com ID {resource_id} não encontrado"
        super().__init__(message=message, code="not_found", status_code=status.HTTP_404_NOT_FOUND)


class ValidationError(AppException):
    """Erro de validação."""

    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(
            message=message, code="validation_error", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details
        )


class AuthenticationError(AppException):
    """Erro de autenticação."""

    def __init__(self, message: str = "Não autenticado"):
        super().__init__(message=message, code="authentication_error", status_code=status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(AppException):
    """Erro de autorização."""

    def __init__(self, message: str = "Acesso negado"):
        super().__init__(message=message, code="authorization_error", status_code=status.HTTP_403_FORBIDDEN)


class ExternalServiceError(AppException):
    """Erro em serviço externo (Twilio, Gemini, etc)."""

    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"Erro no serviço {service}: {message}",
            code="external_service_error",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"service": service},
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra handlers de exceção no app FastAPI."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"AppException: {exc.code} - {exc.message}")
        return JSONResponse(
            status_code=exc.status_code, content={"error": exc.code, "message": exc.message, "details": exc.details}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append({"field": field, "message": error["msg"], "type": error["type"]})

        logger.warning(f"Validation error: {errors}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": "Erro de validação nos dados enviados",
                "details": {"errors": errors},
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"Database error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "database_error", "message": "Erro interno no banco de dados"},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "message": "Erro interno do servidor"},
        )

"""
Exceções específicas para IRIS.
Hierarquia de exceções para tratamento granular de erros.
"""
from typing import Optional, Dict, Any


class IRISException(Exception):
    """Exceção base para todas as exceções da IRIS."""
    
    def __init__(
        self,
        message: str,
        code: str = "IRIS_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário para resposta API."""
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# === Exceções de Segurança ===

class SecurityException(IRISException):
    """Exceções relacionadas a segurança."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "SECURITY_ERROR", details)


class RateLimitExceeded(SecurityException):
    """Rate limit excedido."""
    
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, {"retry_after": retry_after})
        self.retry_after = retry_after


class InvalidInputException(SecurityException):
    """Input inválido ou malicioso detectado."""
    
    def __init__(self, message: str, field: str = None):
        super().__init__(message, {"field": field} if field else None)


# === Exceções de LLM ===

class LLMException(IRISException):
    """Exceções relacionadas ao LLM."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "LLM_ERROR", details)


class LLMTimeoutException(LLMException):
    """LLM demorou muito para responder."""
    
    def __init__(self, timeout_seconds: int = 30):
        super().__init__(
            f"LLM não respondeu em {timeout_seconds} segundos",
            {"timeout": timeout_seconds}
        )


class LLMResponseException(LLMException):
    """Resposta do LLM inválida ou inesperada."""
    
    def __init__(self, message: str, raw_response: str = None):
        details = {"raw_response": raw_response[:500]} if raw_response else None
        super().__init__(message, details)


class EntityExtractionException(LLMException):
    """Falha ao extrair entidades da mensagem."""
    
    def __init__(self, message: str, entity_type: str = None):
        super().__init__(message, {"entity_type": entity_type})


# === Exceções de Agentes ===

class AgentException(IRISException):
    """Exceções dos agentes especializados."""
    
    def __init__(self, message: str, agent: str, details: Optional[Dict] = None):
        full_details = {"agent": agent, **(details or {})}
        super().__init__(message, "AGENT_ERROR", full_details)


class ReminderException(AgentException):
    """Exceções do ReminderAgent."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "ReminderAgent", details)


class FinanceException(AgentException):
    """Exceções do FinanceAgent."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "FinanceAgent", details)


class MeetingException(AgentException):
    """Exceções do MeetingAgent."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "MeetingAgent", details)


class ContactException(AgentException):
    """Exceções do ContactAgent."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "ContactAgent", details)


# === Exceções de Dados ===

class DataException(IRISException):
    """Exceções relacionadas a dados."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "DATA_ERROR", details)


class ValidationException(DataException):
    """Dados inválidos."""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]
        super().__init__(message, details)


class NotFoundException(DataException):
    """Recurso não encontrado."""
    
    def __init__(self, resource: str, identifier: Any = None):
        details = {"resource": resource}
        if identifier:
            details["identifier"] = str(identifier)
        super().__init__(f"{resource} não encontrado", details)


class DatabaseException(DataException):
    """Erro de banco de dados."""
    
    def __init__(self, message: str, operation: str = None):
        super().__init__(message, {"operation": operation})


# === Exceções de Serviços Externos ===

class ExternalServiceException(IRISException):
    """Exceções de serviços externos."""
    
    def __init__(self, service: str, message: str, details: Optional[Dict] = None):
        full_details = {"service": service, **(details or {})}
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", full_details)


class WhatsAppException(ExternalServiceException):
    """Erro no serviço WhatsApp/Twilio."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__("WhatsApp", message, details)


class EmbeddingException(ExternalServiceException):
    """Erro no serviço de embeddings."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__("Embeddings", message, details)


# === Mensagens de Erro Amigáveis ===

FRIENDLY_MESSAGES = {
    "SECURITY_ERROR": "Houve um problema de segurança. Tente novamente.",
    "LLM_ERROR": "Estou com dificuldades técnicas. Tente em instantes.",
    "AGENT_ERROR": "Não consegui processar sua solicitação. Pode reformular?",
    "DATA_ERROR": "Houve um problema com os dados. Verifique e tente novamente.",
    "EXTERNAL_SERVICE_ERROR": "Um serviço externo está indisponível. Tente mais tarde.",
}


def get_friendly_message(exception: IRISException) -> str:
    """Retorna mensagem amigável para o usuário."""
    return FRIENDLY_MESSAGES.get(exception.code, "Ocorreu um erro. Tente novamente.")

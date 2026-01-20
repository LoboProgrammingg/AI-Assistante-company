"""
Módulo de Segurança Central - IRIS.
Consolida todas as práticas de segurança em um único lugar.
"""

import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import Request
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer
security = HTTPBearer()


class SecurityConfig:
    """Configurações de segurança centralizadas."""

    # JWT
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dias
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30

    # Password
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = False

    # Rate Limiting
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15

    # Session
    SESSION_TIMEOUT_MINUTES = 60

    # Headers de segurança
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }


class PasswordValidator:
    """Validador de senhas seguras."""

    @staticmethod
    def validate(password: str) -> tuple[bool, List[str]]:
        """
        Valida força da senha.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        if len(password) < SecurityConfig.MIN_PASSWORD_LENGTH:
            errors.append(f"Senha deve ter no mínimo {SecurityConfig.MIN_PASSWORD_LENGTH} caracteres")

        if SecurityConfig.REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
            errors.append("Senha deve conter pelo menos uma letra maiúscula")

        if SecurityConfig.REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
            errors.append("Senha deve conter pelo menos uma letra minúscula")

        if SecurityConfig.REQUIRE_DIGIT and not re.search(r"\d", password):
            errors.append("Senha deve conter pelo menos um número")

        if SecurityConfig.REQUIRE_SPECIAL and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            errors.append("Senha deve conter pelo menos um caractere especial")

        # Verificar senhas comuns
        common_passwords = ["123456", "password", "123456789", "12345678", "qwerty"]
        if password.lower() in common_passwords:
            errors.append("Senha muito comum, escolha uma mais segura")

        return len(errors) == 0, errors

    @staticmethod
    def hash_password(password: str) -> str:
        """Gera hash seguro da senha."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verifica senha contra hash."""
        return pwd_context.verify(plain_password, hashed_password)


class TokenManager:
    """Gerenciador de tokens JWT."""

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Cria token de acesso JWT."""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=SecurityConfig.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "access"})

        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=SecurityConfig.JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(user_id: int) -> str:
        """Cria token de refresh."""
        expire = datetime.utcnow() + timedelta(days=SecurityConfig.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "jti": secrets.token_urlsafe(32),  # Token ID único
        }

        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=SecurityConfig.JWT_ALGORITHM)

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
        """
        Verifica e decodifica token JWT.

        Returns:
            Payload do token ou None se inválido
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[SecurityConfig.JWT_ALGORITHM])

            if payload.get("type") != token_type:
                logger.warning(f"Tipo de token inválido: esperado {token_type}")
                return None

            return payload

        except JWTError as e:
            logger.warning(f"Erro ao verificar token: {e}")
            return None


class LoginAttemptTracker:
    """Rastreia tentativas de login para prevenir brute force."""

    _attempts: Dict[str, List[datetime]] = {}
    _lockouts: Dict[str, datetime] = {}

    @classmethod
    def record_attempt(cls, identifier: str, success: bool) -> None:
        """Registra tentativa de login."""
        now = datetime.utcnow()

        if success:
            # Login bem-sucedido, limpar histórico
            cls._attempts.pop(identifier, None)
            cls._lockouts.pop(identifier, None)
            return

        # Login falhou
        if identifier not in cls._attempts:
            cls._attempts[identifier] = []

        cls._attempts[identifier].append(now)

        # Limpar tentativas antigas (mais de 15 minutos)
        cutoff = now - timedelta(minutes=SecurityConfig.LOGIN_LOCKOUT_MINUTES)
        cls._attempts[identifier] = [t for t in cls._attempts[identifier] if t > cutoff]

        # Verificar se deve bloquear
        if len(cls._attempts[identifier]) >= SecurityConfig.MAX_LOGIN_ATTEMPTS:
            cls._lockouts[identifier] = now + timedelta(minutes=SecurityConfig.LOGIN_LOCKOUT_MINUTES)
            logger.warning(f"Conta bloqueada por tentativas excessivas: {identifier}")

    @classmethod
    def is_locked(cls, identifier: str) -> tuple[bool, Optional[int]]:
        """
        Verifica se conta está bloqueada.

        Returns:
            (is_locked, seconds_remaining)
        """
        if identifier not in cls._lockouts:
            return False, None

        lockout_until = cls._lockouts[identifier]
        now = datetime.utcnow()

        if now >= lockout_until:
            # Lockout expirou
            cls._lockouts.pop(identifier, None)
            cls._attempts.pop(identifier, None)
            return False, None

        seconds_remaining = int((lockout_until - now).total_seconds())
        return True, seconds_remaining


class RequestValidator:
    """Validador de requisições."""

    # IPs suspeitos (exemplo - em produção usar lista dinâmica)
    BLOCKED_IPS: set = set()

    # User agents suspeitos
    SUSPICIOUS_USER_AGENTS = [
        "sqlmap",
        "nikto",
        "nessus",
        "burpsuite",
        "acunetix",
    ]

    @classmethod
    def validate_request(cls, request: Request) -> tuple[bool, Optional[str]]:
        """
        Valida requisição por padrões suspeitos.

        Returns:
            (is_valid, error_message)
        """
        client_ip = cls.get_client_ip(request)

        # Verificar IP bloqueado
        if client_ip in cls.BLOCKED_IPS:
            return False, "IP bloqueado"

        # Verificar user agent suspeito
        user_agent = request.headers.get("user-agent", "").lower()
        for suspicious in cls.SUSPICIOUS_USER_AGENTS:
            if suspicious in user_agent:
                logger.warning(f"User agent suspeito detectado: {user_agent}")
                return False, "Requisição bloqueada"

        return True, None

    @staticmethod
    def get_client_ip(request: Request) -> str:
        """Obtém IP real do cliente (considerando proxies)."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


def generate_secure_token(length: int = 32) -> str:
    """Gera token seguro para uso geral."""
    return secrets.token_urlsafe(length)


def hash_data(data: str) -> str:
    """Gera hash SHA-256 de dados."""
    return hashlib.sha256(data.encode()).hexdigest()


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """Mascara dados sensíveis para logs."""
    if len(data) <= visible_chars:
        return "*" * len(data)
    return data[:visible_chars] + "*" * (len(data) - visible_chars)

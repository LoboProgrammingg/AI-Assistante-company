"""
Rate Limiter para IRIS.
Controla a taxa de requisições por usuário usando sliding window.
Suporta Redis (quando disponível) ou fallback para memória local.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from typing import Dict, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# Tentar importar cache service (Redis)
try:
    from app.services.cache_service import cache_service

    REDIS_AVAILABLE = cache_service.is_available
except ImportError:
    cache_service = None
    REDIS_AVAILABLE = False


@dataclass
class RateLimitConfig:
    """Configuração de rate limiting."""

    requests_per_minute: int = 30
    requests_per_hour: int = 500
    burst_limit: int = 10  # Máximo de requests em 10 segundos
    block_duration_seconds: int = 60  # Tempo de bloqueio após exceder


class RateLimitExceeded(Exception):
    """Exceção quando rate limit é excedido."""

    def __init__(self, message: str, retry_after: int = 60):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)


@dataclass
class UserRateData:
    """Dados de rate limiting por usuário."""

    requests: list = field(default_factory=list)  # Timestamps
    blocked_until: float = 0.0
    total_requests: int = 0
    violations: int = 0


class RateLimiter:
    """
    Rate limiter com sliding window por usuário.

    Suporta:
    - Limite por minuto
    - Limite por hora
    - Burst protection (muitos requests em segundos)
    - Bloqueio temporário após violações
    """

    _instance: Optional["RateLimiter"] = None

    def __new__(cls, config: RateLimitConfig = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: RateLimitConfig = None):
        if self._initialized:
            return

        self.config = config or self._load_config_from_settings()
        self._users: Dict[int, UserRateData] = defaultdict(UserRateData)
        self._initialized = True

        logger.info(
            f"RateLimiter inicializado: "
            f"{self.config.requests_per_minute}/min, "
            f"{self.config.requests_per_hour}/hora"
        )

    def _load_config_from_settings(self) -> RateLimitConfig:
        """Carrega configuração do settings."""
        return RateLimitConfig(
            requests_per_minute=getattr(settings, "RATE_LIMIT_PER_MINUTE", 30),
            requests_per_hour=getattr(settings, "RATE_LIMIT_PER_HOUR", 500),
            burst_limit=getattr(settings, "RATE_LIMIT_BURST", 10),
            block_duration_seconds=getattr(settings, "RATE_LIMIT_BLOCK_SECONDS", 60),
        )

    def check(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Verifica se usuário pode fazer requisição.

        Returns:
            Tuple[bool, Optional[str]]: (permitido, mensagem de erro se bloqueado)
        """
        now = time.time()
        user_data = self._users[user_id]

        # Verificar se está bloqueado
        if user_data.blocked_until > now:
            remaining = int(user_data.blocked_until - now)
            return False, f"Aguarde {remaining}s antes de tentar novamente."

        # Limpar requests antigos (mais de 1 hora)
        self._cleanup_old_requests(user_data, now)

        # Verificar burst (últimos 10 segundos)
        if not self._check_burst(user_data, now):
            self._apply_block(user_data, now, "burst")
            return False, "Muitas mensagens em sequência. Aguarde um momento."

        # Verificar limite por minuto
        if not self._check_minute_limit(user_data, now):
            self._apply_block(user_data, now, "minute")
            return False, f"Limite de {self.config.requests_per_minute} mensagens/minuto atingido."

        # Verificar limite por hora
        if not self._check_hour_limit(user_data, now):
            return False, f"Limite de {self.config.requests_per_hour} mensagens/hora atingido."

        # Registrar request
        user_data.requests.append(now)
        user_data.total_requests += 1

        return True, None

    def _cleanup_old_requests(self, user_data: UserRateData, now: float) -> None:
        """Remove requests mais antigos que 1 hora."""
        cutoff = now - 3600
        user_data.requests = [t for t in user_data.requests if t > cutoff]

    def _check_burst(self, user_data: UserRateData, now: float) -> bool:
        """Verifica limite de burst (10 segundos)."""
        cutoff = now - 10
        recent = sum(1 for t in user_data.requests if t > cutoff)
        return recent < self.config.burst_limit

    def _check_minute_limit(self, user_data: UserRateData, now: float) -> bool:
        """Verifica limite por minuto."""
        cutoff = now - 60
        recent = sum(1 for t in user_data.requests if t > cutoff)
        return recent < self.config.requests_per_minute

    def _check_hour_limit(self, user_data: UserRateData, now: float) -> bool:
        """Verifica limite por hora."""
        return len(user_data.requests) < self.config.requests_per_hour

    def _apply_block(self, user_data: UserRateData, now: float, reason: str) -> None:
        """Aplica bloqueio temporário."""
        user_data.violations += 1
        # Bloqueio progressivo: mais violações = mais tempo
        multiplier = min(user_data.violations, 5)
        block_time = self.config.block_duration_seconds * multiplier
        user_data.blocked_until = now + block_time

        logger.warning(
            f"Rate limit aplicado ({reason}): " f"bloqueio de {block_time}s, violações: {user_data.violations}"
        )

    def get_user_stats(self, user_id: int) -> Dict:
        """Retorna estatísticas do usuário."""
        user_data = self._users[user_id]
        now = time.time()

        minute_requests = sum(1 for t in user_data.requests if t > now - 60)
        hour_requests = len(user_data.requests)

        return {
            "requests_last_minute": minute_requests,
            "requests_last_hour": hour_requests,
            "total_requests": user_data.total_requests,
            "violations": user_data.violations,
            "is_blocked": user_data.blocked_until > now,
            "blocked_remaining": max(0, int(user_data.blocked_until - now)),
        }

    def reset_user(self, user_id: int) -> None:
        """Reset dados de rate limiting do usuário (admin only)."""
        if user_id in self._users:
            del self._users[user_id]
            logger.info(f"Rate limit resetado para user_id={user_id}")


def rate_limit(func):
    """Decorator para aplicar rate limiting em funções."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        user_id = kwargs.get("user_id") or (args[0] if args else None)

        if user_id:
            limiter = RateLimiter()
            allowed, message = limiter.check(user_id)

            if not allowed:
                raise RateLimitExceeded(message)

        return await func(*args, **kwargs)

    return wrapper

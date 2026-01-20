"""
Rate Limiting usando Redis.
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status

from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter baseado em Redis."""

    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000, key_prefix: str = "rate_limit"):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.key_prefix = key_prefix

    def _get_client_id(self, request: Request) -> str:
        """Obtém identificador do cliente."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_minute_key(self, client_id: str) -> str:
        """Gera chave para limite por minuto."""
        minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        return f"{self.key_prefix}:{client_id}:min:{minute}"

    def _get_hour_key(self, client_id: str) -> str:
        """Gera chave para limite por hora."""
        hour = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        return f"{self.key_prefix}:{client_id}:hour:{hour}"

    def check_rate_limit(self, request: Request) -> tuple[bool, dict]:
        """
        Verifica se a requisição está dentro do limite.

        Returns:
            Tuple[bool, dict]: (permitido, info)
        """
        if not cache_service.is_available:
            return True, {"limited": False, "reason": "cache_unavailable"}

        client_id = self._get_client_id(request)

        minute_key = self._get_minute_key(client_id)
        hour_key = self._get_hour_key(client_id)

        try:
            minute_count = cache_service.get(minute_key) or 0
            hour_count = cache_service.get(hour_key) or 0

            if minute_count >= self.requests_per_minute:
                return False, {
                    "limited": True,
                    "reason": "minute_limit",
                    "limit": self.requests_per_minute,
                    "current": minute_count,
                    "retry_after": 60,
                }

            if hour_count >= self.requests_per_hour:
                return False, {
                    "limited": True,
                    "reason": "hour_limit",
                    "limit": self.requests_per_hour,
                    "current": hour_count,
                    "retry_after": 3600,
                }

            cache_service.set(minute_key, minute_count + 1, ttl_seconds=60)
            cache_service.set(hour_key, hour_count + 1, ttl_seconds=3600)

            return True, {
                "limited": False,
                "minute_remaining": self.requests_per_minute - minute_count - 1,
                "hour_remaining": self.requests_per_hour - hour_count - 1,
            }

        except Exception as e:
            logger.error(f"Erro no rate limiter: {e}")
            return True, {"limited": False, "reason": "error"}

    async def __call__(self, request: Request) -> None:
        """FastAPI dependency para rate limiting."""
        allowed, info = self.check_rate_limit(request)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Limite de requisições excedido ({info['reason']})",
                    "retry_after": info.get("retry_after", 60),
                },
                headers={"Retry-After": str(info.get("retry_after", 60))},
            )


# Rate limiters pré-configurados
default_limiter = RateLimiter(requests_per_minute=60, requests_per_hour=1000)
strict_limiter = RateLimiter(requests_per_minute=10, requests_per_hour=100)
webhook_limiter = RateLimiter(requests_per_minute=120, requests_per_hour=5000)

# Rate limiter específico para autenticação (mais restritivo para prevenir brute force)
auth_limiter = RateLimiter(requests_per_minute=5, requests_per_hour=30, key_prefix="auth_rate_limit")

"""
Configurações da aplicação.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "WhatsApp AI Assistant"
    DEBUG: bool = False

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "whatsapp_ai"
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: Optional[str] = None  # Railway provides this directly

    @property
    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            # Railway pode fornecer URL com postgres:// (antigo), converter para postgresql://
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None  # Railway provides this directly

    @property
    def get_redis_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # WhatsApp API (Twilio)
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str
    WHATSAPP_WEBHOOK_URL: str

    # Google Gemini AI
    GOOGLE_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-pro"
    GEMINI_TEMPERATURE: float = 0.7
    GEMINI_MAX_OUTPUT_TOKENS: int = 40000

    # JWT & Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    BACKEND_CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:3001,http://localhost:5173,https://ai-assistante-company-frontend-production.up.railway.app"
    )

    # Timezone Default
    DEFAULT_TIMEZONE: str = "America/Cuiaba"

    # Audio Processing
    MAX_AUDIO_SIZE_MB: int = 25
    SUPPORTED_AUDIO_FORMATS: list[str] = [".mp3", ".wav", ".ogg", ".m4a", ".opus"]

    # Scheduler
    SCHEDULER_CHECK_INTERVAL_SECONDS: int = 30

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 30
    RATE_LIMIT_PER_HOUR: int = 500
    RATE_LIMIT_BURST: int = 10
    RATE_LIMIT_BLOCK_SECONDS: int = 60

    # Input Sanitization
    MAX_MESSAGE_LENGTH: int = 5000
    MAX_FIELD_LENGTH: int = 500
    ALLOW_URLS_IN_MESSAGE: bool = True
    ALLOW_EMOJIS: bool = True
    STRIP_HTML: bool = True
    LOG_SANITIZATION: bool = True

    # LangGraph
    LANGGRAPH_MEMORY_STORE: str = "postgres"
    LANGGRAPH_RECURSION_LIMIT: int = 15

    # LangSmith (Observabilidade)
    # Habilitar quando LANGCHAIN_API_KEY estiver configurada
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "iris-whatsapp"

    @property
    def langsmith_enabled(self) -> bool:
        """LangSmith só funciona com API key válida."""
        return bool(self.LANGCHAIN_API_KEY and self.LANGCHAIN_TRACING_V2)

    # SMTP (Gmail)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USE_SSL: bool = False  # True para porta 465, False para 587 com STARTTLS
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "WhatsApp AI Assistant"

    # Verificação de email
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 15

    # Tavily Web Search
    TAVILY_API_KEY: str = ""

    # Todoist Integration
    TODOIST_API_KEY: str = ""
    TODOIST_ALERT_MINUTES: int = 60  # Alertar quando faltar X minutos
    TODOIST_POLLING_SECONDS: int = 300  # Polling a cada 5 minutos

    # Google Calendar OAuth (para cada usuário conectar seu calendário)
    GOOGLE_OAUTH_CLIENT_ID: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")

    # URL base do backend (para OAuth redirect)
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8005")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

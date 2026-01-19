"""
Configurações da aplicação.
"""
import os
from functools import lru_cache
from typing import Optional
from pydantic import field_validator, BaseSettings


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
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # WhatsApp API (Twilio)
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str
    WHATSAPP_WEBHOOK_URL: str
    
    # Google Gemini AI
    GOOGLE_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.7
    GEMINI_MAX_OUTPUT_TOKENS: int = 40000
    
    # JWT & Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # CORS
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str) and not v:
            return ["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"]
        return v
    
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000", 
        "http://localhost:3001", 
        "http://localhost:5173",
        "https://ai-assistante-company-frontend-production.up.railway.app"
    ]
    
    # Timezone Default
    DEFAULT_TIMEZONE: str = "America/Cuiaba"
    
    # Audio Processing
    MAX_AUDIO_SIZE_MB: int = 25
    SUPPORTED_AUDIO_FORMATS: list[str] = [".mp3", ".wav", ".ogg", ".m4a", ".opus"]
    
    # Scheduler
    SCHEDULER_CHECK_INTERVAL_SECONDS: int = 30
    
    # LangGraph
    LANGGRAPH_MEMORY_STORE: str = "postgres"
    
    # SMTP (Gmail)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "WhatsApp AI Assistant"
    
    # Verificação de email
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 15
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


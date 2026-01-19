from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import logging

from app.config import settings
from app.database import engine
from app.models import Base
from app.api import api_router
from app.api.rate_limiter import RateLimiter
from app.api.exceptions import register_exception_handlers

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar tabelas
Base.metadata.create_all(bind=engine)

# Inicializar FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Registrar exception handlers
register_exception_handlers(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiter
rate_limiter = RateLimiter(requests_per_minute=60, requests_per_hour=1000)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Middleware de rate limiting para todas as requisições."""
    # Ignorar health check e docs
    if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)
    
    allowed, info = rate_limiter.check_rate_limit(request)
    
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "message": f"Limite de requisições excedido",
                "retry_after": info.get("retry_after", 60)
            },
            headers={"Retry-After": str(info.get("retry_after", 60))}
        )
    
    response = await call_next(request)
    
    # Adicionar headers de rate limit info
    if info.get("minute_remaining") is not None:
        response.headers["X-RateLimit-Remaining"] = str(info["minute_remaining"])
    
    return response

# Registrar API Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "WhatsApp AI Assistant API", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check básico."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/health/detailed")
async def health_check_detailed():
    """Health check detalhado com status de todos os serviços."""
    from app.database import SessionLocal
    from app.services.cache_service import cache_service
    
    services = {}
    overall_healthy = True
    
    # Verificar PostgreSQL
    try:
        from sqlalchemy import text
        import time
        db = SessionLocal()
        start = time.time()
        db.execute(text("SELECT 1"))
        latency = round((time.time() - start) * 1000, 2)
        db.close()
        services["postgres"] = {"status": "healthy", "latency_ms": latency}
    except Exception as e:
        services["postgres"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Verificar Redis
    if cache_service.is_available:
        services["redis"] = {"status": "healthy"}
    else:
        services["redis"] = {"status": "unhealthy", "error": "Conexão não disponível"}
        overall_healthy = False
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": services,
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
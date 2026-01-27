from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.finances import router as finances_router
from app.api.integrations import router as integrations_router
from app.api.meetings import router as meetings_router
from app.api.metrics import router as metrics_router
from app.api.reminders import router as reminders_router
from app.api.tasks import router as tasks_router
from app.api.users import router as users_router
from app.api.webhooks import router as webhooks_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(reminders_router)
api_router.include_router(finances_router)
api_router.include_router(meetings_router)
api_router.include_router(tasks_router)
api_router.include_router(chat_router)
api_router.include_router(webhooks_router)
api_router.include_router(documents_router)
api_router.include_router(metrics_router)
api_router.include_router(integrations_router)

__all__ = ["api_router"]

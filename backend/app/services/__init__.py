from app.services.auth_service import AuthService
from app.services.cache_service import CacheService, cache_service
from app.services.email_service import EmailService, email_service
from app.services.finance_service import FinanceService
from app.services.meeting_service import MeetingService
from app.services.memory_service import MemoryService
from app.services.reminder_service import ReminderService
from app.services.task_service import TaskService

__all__ = [
    "ReminderService",
    "FinanceService",
    "MeetingService",
    "MemoryService",
    "TaskService",
    "CacheService",
    "cache_service",
    "EmailService",
    "email_service",
    "AuthService",
]

try:
    from app.services.whatsapp_service import WhatsAppService, WhatsAppWebhookHandler

    __all__.extend(["WhatsAppService", "WhatsAppWebhookHandler"])
except ImportError:
    pass

"""
Módulo de email para IRIS.

Exporta o serviço de email e templates.
"""

from app.services.email.service import EmailService, email_service
from app.services.email.templates import EmailTemplates

__all__ = ["EmailService", "email_service", "EmailTemplates"]

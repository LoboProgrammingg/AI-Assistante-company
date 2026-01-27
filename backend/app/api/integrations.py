"""
Endpoints para integrações de terceiros (Google Calendar, etc).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.models import User
from app.services.google_calendar_service import GoogleCalendarService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


class IntegrationStatus(BaseModel):
    provider: str
    connected: bool
    account_email: Optional[str] = None
    account_name: Optional[str] = None


class ConnectResponse(BaseModel):
    authorization_url: str


class DisconnectResponse(BaseModel):
    success: bool
    message: str


# ============================================================================
# Google Calendar
# ============================================================================


@router.get("/google-calendar/status", response_model=IntegrationStatus)
async def google_calendar_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verifica status da integração Google Calendar."""
    service = GoogleCalendarService(db)
    integration = service.get_user_integration(current_user.id)

    if integration:
        return IntegrationStatus(
            provider="google_calendar",
            connected=True,
            account_email=integration.account_email,
            account_name=integration.account_name,
        )

    return IntegrationStatus(provider="google_calendar", connected=False)


@router.get("/google-calendar/connect", response_model=ConnectResponse)
async def google_calendar_connect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Inicia fluxo de conexão com Google Calendar."""
    service = GoogleCalendarService(db)

    if not service.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Google Calendar OAuth não está configurado no servidor",
        )

    # State inclui user_id para identificar no callback
    state = f"{current_user.id}"
    authorization_url = service.get_authorization_url(current_user.id, state)

    if not authorization_url:
        raise HTTPException(status_code=500, detail="Erro ao gerar URL de autorização")

    return ConnectResponse(authorization_url=authorization_url)


@router.get("/google-calendar/callback")
async def google_calendar_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Callback OAuth do Google Calendar."""
    # URL do frontend para redirecionar
    frontend_url = settings.FRONTEND_URL

    if error:
        logger.error(f"OAuth error: {error}")
        return RedirectResponse(url=f"{frontend_url}/settings?integration=google_calendar&status=error&message={error}")

    try:
        user_id = int(state)
    except (ValueError, TypeError):
        return RedirectResponse(
            url=f"{frontend_url}/settings?integration=google_calendar&status=error&message=invalid_state"
        )

    service = GoogleCalendarService(db)
    result = service.handle_oauth_callback(code, user_id)

    if result.get("success"):
        return RedirectResponse(
            url=f"{frontend_url}/settings?integration=google_calendar&status=success&email={result.get('email', '')}"
        )
    else:
        error_msg = result.get("error", "unknown_error")
        return RedirectResponse(
            url=f"{frontend_url}/settings?integration=google_calendar&status=error&message={error_msg}"
        )


@router.delete("/google-calendar/disconnect", response_model=DisconnectResponse)
async def google_calendar_disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Desconecta integração Google Calendar."""
    service = GoogleCalendarService(db)
    success = service.disconnect(current_user.id)

    if success:
        return DisconnectResponse(success=True, message="Google Calendar desconectado")
    else:
        raise HTTPException(status_code=500, detail="Erro ao desconectar")


# ============================================================================
# Listar todas as integrações disponíveis
# ============================================================================


@router.get("/available")
async def list_available_integrations():
    """Lista integrações disponíveis e seu status de configuração."""
    return {
        "integrations": [
            {
                "provider": "google_calendar",
                "name": "Google Calendar",
                "description": "Sincronize eventos e crie reuniões com Google Meet",
                "configured": bool(settings.GOOGLE_OAUTH_CLIENT_ID),
                "icon": "calendar",
            },
        ]
    }

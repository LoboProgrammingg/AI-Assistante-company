"""
Serviço de integração Google Calendar com OAuth 2.0 por usuário.
Cada usuário conecta sua própria conta Google e a IA acessa seu calendário pessoal.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import UserIntegration

# Google APIs - imports condicionais
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    Credentials = None
    Flow = None
    build = None
    HttpError = Exception

logger = logging.getLogger(__name__)

# Scopes necessários para o Google Calendar
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


class GoogleCalendarService:
    """Serviço para gerenciar integrações do Google Calendar por usuário."""

    PROVIDER = "google_calendar"

    def __init__(self, db: Session):
        self.db = db
        self._client_config = self._load_client_config()

    def _load_client_config(self) -> Optional[dict]:
        """Carrega configuração OAuth do Google."""
        client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None)
        client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", None)

        if not client_id or not client_secret:
            logger.warning("Google OAuth não configurado (GOOGLE_OAUTH_CLIENT_ID/SECRET)")
            return None

        return {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self._get_redirect_uri()],
            }
        }

    def _get_redirect_uri(self) -> str:
        """Retorna a URI de redirecionamento OAuth."""
        base_url = getattr(settings, "BACKEND_URL", "http://localhost:8005")
        return f"{base_url}/api/v1/integrations/google-calendar/callback"

    @property
    def is_configured(self) -> bool:
        """Verifica se o OAuth está configurado."""
        return self._client_config is not None

    def get_user_integration(self, user_id: int) -> Optional[UserIntegration]:
        """Busca integração do usuário."""
        return (
            self.db.query(UserIntegration)
            .filter(
                UserIntegration.user_id == user_id,
                UserIntegration.provider == self.PROVIDER,
                UserIntegration.is_active == True,
            )
            .first()
        )

    def is_user_connected(self, user_id: int) -> bool:
        """Verifica se o usuário tem Google Calendar conectado."""
        integration = self.get_user_integration(user_id)
        return integration is not None

    def get_authorization_url(self, user_id: int, state: str = None) -> Optional[str]:
        """Gera URL para autorização OAuth."""
        if not self.is_configured:
            return None

        flow = Flow.from_client_config(
            self._client_config,
            scopes=SCOPES,
            redirect_uri=self._get_redirect_uri(),
        )

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state or str(user_id),
        )

        return authorization_url

    def handle_oauth_callback(self, code: str, user_id: int) -> dict:
        """Processa callback do OAuth e salva tokens."""
        if not self.is_configured:
            return {"success": False, "error": "OAuth não configurado"}

        try:
            flow = Flow.from_client_config(
                self._client_config,
                scopes=SCOPES,
                redirect_uri=self._get_redirect_uri(),
            )

            flow.fetch_token(code=code)
            credentials = flow.credentials

            # Buscar informações do usuário Google
            user_info = self._get_google_user_info(credentials)

            # Remover integração anterior se existir
            self.db.query(UserIntegration).filter(
                UserIntegration.user_id == user_id,
                UserIntegration.provider == self.PROVIDER,
            ).delete()

            # Criar nova integração
            integration = UserIntegration(
                user_id=user_id,
                provider=self.PROVIDER,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expiry=credentials.expiry,
                account_email=user_info.get("email"),
                account_name=user_info.get("name"),
                scopes=list(credentials.scopes) if credentials.scopes else SCOPES,
                is_active=True,
            )

            self.db.add(integration)
            self.db.commit()

            logger.info(f"Google Calendar conectado para user {user_id}: {user_info.get('email')}")

            return {
                "success": True,
                "email": user_info.get("email"),
                "name": user_info.get("name"),
            }

        except Exception as e:
            logger.error(f"Erro no OAuth callback: {e}")
            return {"success": False, "error": str(e)}

    def _get_google_user_info(self, credentials: Credentials) -> dict:
        """Busca informações do usuário Google."""
        try:
            service = build("oauth2", "v2", credentials=credentials)
            user_info = service.userinfo().get().execute()
            return user_info
        except Exception as e:
            logger.warning(f"Erro ao buscar user info: {e}")
            return {}

    def disconnect(self, user_id: int) -> bool:
        """Desconecta a integração do usuário."""
        try:
            self.db.query(UserIntegration).filter(
                UserIntegration.user_id == user_id,
                UserIntegration.provider == self.PROVIDER,
            ).delete()
            self.db.commit()
            logger.info(f"Google Calendar desconectado para user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Erro ao desconectar: {e}")
            return False

    def _get_credentials(self, user_id: int) -> Optional[Credentials]:
        """Obtém credenciais OAuth do usuário, renovando se necessário."""
        integration = self.get_user_integration(user_id)
        if not integration:
            return None

        credentials = Credentials(
            token=integration.access_token,
            refresh_token=integration.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._client_config["web"]["client_id"],
            client_secret=self._client_config["web"]["client_secret"],
            scopes=integration.scopes or SCOPES,
        )

        # Verificar se precisa renovar
        if integration.token_expiry and integration.token_expiry < datetime.now(timezone.utc):
            try:
                from google.auth.transport.requests import Request

                credentials.refresh(Request())

                # Atualizar tokens no banco
                integration.access_token = credentials.token
                integration.token_expiry = credentials.expiry
                integration.updated_at = datetime.now(timezone.utc)
                self.db.commit()
                logger.info(f"Token renovado para user {user_id}")
            except Exception as e:
                logger.error(f"Erro ao renovar token: {e}")
                integration.is_active = False
                self.db.commit()
                return None

        # Atualizar last_used_at
        integration.last_used_at = datetime.now(timezone.utc)
        self.db.commit()

        return credentials

    def list_events(
        self,
        user_id: int,
        max_results: int = 10,
        time_min: datetime = None,
        time_max: datetime = None,
    ) -> dict:
        """Lista eventos do calendário do usuário."""
        credentials = self._get_credentials(user_id)
        if not credentials:
            return {"success": False, "error": "Google Calendar não conectado"}

        try:
            service = build("calendar", "v3", credentials=credentials)

            if not time_min:
                time_min = datetime.now(timezone.utc)

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat() if time_max else None,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])

            return {
                "success": True,
                "events": [
                    {
                        "id": e.get("id"),
                        "title": e.get("summary", "Sem título"),
                        "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                        "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
                        "location": e.get("location"),
                        "description": e.get("description"),
                        "attendees": [a.get("email") for a in e.get("attendees", [])],
                        "meet_link": e.get("hangoutLink"),
                    }
                    for e in events
                ],
            }

        except HttpError as e:
            logger.error(f"Erro ao listar eventos: {e}")
            return {"success": False, "error": str(e)}

    def create_event(
        self,
        user_id: int,
        title: str,
        start_time: datetime,
        end_time: datetime = None,
        description: str = None,
        location: str = None,
        attendees: list = None,
        add_meet: bool = False,
    ) -> dict:
        """Cria evento no calendário do usuário."""
        credentials = self._get_credentials(user_id)
        if not credentials:
            return {"success": False, "error": "Google Calendar não conectado"}

        try:
            service = build("calendar", "v3", credentials=credentials)

            if not end_time:
                end_time = start_time + timedelta(hours=1)

            event = {
                "summary": title,
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "America/Sao_Paulo",
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "America/Sao_Paulo",
                },
            }

            if description:
                event["description"] = description

            if location:
                event["location"] = location

            if attendees:
                event["attendees"] = [{"email": email} for email in attendees]

            if add_meet:
                event["conferenceData"] = {
                    "createRequest": {
                        "requestId": f"meet-{datetime.now().timestamp()}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                }

            created_event = (
                service.events()
                .insert(
                    calendarId="primary",
                    body=event,
                    conferenceDataVersion=1 if add_meet else 0,
                    sendUpdates="all" if attendees else "none",
                )
                .execute()
            )

            return {
                "success": True,
                "event": {
                    "id": created_event.get("id"),
                    "title": created_event.get("summary"),
                    "start": created_event.get("start", {}).get("dateTime"),
                    "end": created_event.get("end", {}).get("dateTime"),
                    "link": created_event.get("htmlLink"),
                    "meet_link": created_event.get("hangoutLink"),
                },
            }

        except HttpError as e:
            logger.error(f"Erro ao criar evento: {e}")
            return {"success": False, "error": str(e)}

    def check_availability(
        self,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Verifica disponibilidade no calendário do usuário."""
        credentials = self._get_credentials(user_id)
        if not credentials:
            return {"success": False, "error": "Google Calendar não conectado"}

        try:
            service = build("calendar", "v3", credentials=credentials)

            body = {
                "timeMin": start_time.isoformat(),
                "timeMax": end_time.isoformat(),
                "items": [{"id": "primary"}],
            }

            result = service.freebusy().query(body=body).execute()
            busy_times = result.get("calendars", {}).get("primary", {}).get("busy", [])

            return {
                "success": True,
                "is_free": len(busy_times) == 0,
                "busy_times": busy_times,
            }

        except HttpError as e:
            logger.error(f"Erro ao verificar disponibilidade: {e}")
            return {"success": False, "error": str(e)}

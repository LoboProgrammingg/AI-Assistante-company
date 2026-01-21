"""
Google Calendar - Integração com agenda do Google.
Docs: https://developers.google.com/calendar/api
"""

import logging
import json
import base64
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def get_calendar_service(user_credentials: dict = None):
    """
    Obtém serviço do Google Calendar.
    Usa Service Account para operações do sistema ou OAuth para usuário.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from app.config import settings
        
        # Tentar carregar credenciais de Service Account
        creds = None
        
        if settings.GOOGLE_CREDENTIALS_JSON:
            # Primeiro, tenta como caminho de arquivo
            try:
                with open(settings.GOOGLE_CREDENTIALS_JSON, 'r') as f:
                    creds_data = json.load(f)
                creds = service_account.Credentials.from_service_account_info(
                    creds_data,
                    scopes=['https://www.googleapis.com/auth/calendar']
                )
            except (FileNotFoundError, json.JSONDecodeError):
                # Se não for arquivo, tenta como JSON base64 (para Railway)
                try:
                    creds_json = base64.b64decode(settings.GOOGLE_CREDENTIALS_JSON).decode('utf-8')
                    creds_data = json.loads(creds_json)
                    creds = service_account.Credentials.from_service_account_info(
                        creds_data,
                        scopes=['https://www.googleapis.com/auth/calendar']
                    )
                except Exception as e:
                    logger.error(f"[GCAL] Erro ao decodificar credenciais: {e}")
                    return None
        
        if not creds:
            logger.warning("[GCAL] Credenciais não configuradas")
            return None
        
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"[GCAL] Erro ao criar serviço: {e}")
        return None


class GoogleCalendarTools:
    """Tools para integração com Google Calendar."""

    def __init__(self):
        self.service = None

    def _get_service(self):
        if not self.service:
            self.service = get_calendar_service()
        return self.service

    @property
    def is_configured(self) -> bool:
        from app.config import settings
        return bool(settings.GOOGLE_CREDENTIALS_JSON)

    def get_tools(self) -> list:
        if not self.is_configured:
            logger.warning("[GCAL] Google Calendar não configurado")
            return []
        return [
            self._listar_eventos,
            self._criar_evento,
            self._verificar_disponibilidade,
        ]

    @tool
    def _listar_eventos(data: str = None, dias: int = 7) -> str:
        """
        Lista eventos da agenda.
        
        Args:
            data: Data inicial (formato: YYYY-MM-DD). Padrão: hoje
            dias: Número de dias a consultar (1-30)
        """
        try:
            service = get_calendar_service()
            if not service:
                return "Google Calendar não configurado."
            
            if data:
                start = datetime.fromisoformat(data)
            else:
                start = datetime.now()
            
            end = start + timedelta(days=min(dias, 30))
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=start.isoformat() + 'Z',
                timeMax=end.isoformat() + 'Z',
                maxResults=20,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return f"Nenhum evento nos próximos {dias} dias."
            
            resultado = [f"Eventos de {start.strftime('%d/%m')} a {end.strftime('%d/%m')}:"]
            for event in events:
                start_time = event['start'].get('dateTime', event['start'].get('date'))
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                resultado.append(f"- {dt.strftime('%d/%m %H:%M')}: {event['summary']}")
            
            return "\n".join(resultado)
        except Exception as e:
            logger.error(f"[GCAL] Erro ao listar eventos: {e}")
            return f"Erro ao listar eventos: {str(e)}"

    @tool
    def _criar_evento(
        titulo: str,
        data_hora: str,
        duracao_minutos: int = 60,
        descricao: str = "",
        participantes: str = ""
    ) -> str:
        """
        Cria um evento no Google Calendar.
        
        Args:
            titulo: Título do evento
            data_hora: Data e hora (formato: YYYY-MM-DD HH:MM)
            duracao_minutos: Duração em minutos (padrão: 60)
            descricao: Descrição do evento (opcional)
            participantes: Emails separados por vírgula (opcional)
        """
        try:
            service = get_calendar_service()
            if not service:
                return "Google Calendar não configurado."
            
            start = datetime.fromisoformat(data_hora.replace(' ', 'T'))
            end = start + timedelta(minutes=duracao_minutos)
            
            event = {
                'summary': titulo,
                'description': descricao,
                'start': {'dateTime': start.isoformat(), 'timeZone': 'America/Cuiaba'},
                'end': {'dateTime': end.isoformat(), 'timeZone': 'America/Cuiaba'},
                'conferenceData': {
                    'createRequest': {'requestId': f"iris-{datetime.now().timestamp()}"}
                },
            }
            
            if participantes:
                emails = [e.strip() for e in participantes.split(',') if e.strip()]
                event['attendees'] = [{'email': email} for email in emails]
            
            created = service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1,
                sendUpdates='all' if participantes else 'none'
            ).execute()
            
            meet_link = created.get('hangoutLink', '')
            msg = f"Evento '{titulo}' criado para {start.strftime('%d/%m às %H:%M')}."
            if meet_link:
                msg += f"\nLink do Meet: {meet_link}"
            
            return msg
        except Exception as e:
            logger.error(f"[GCAL] Erro ao criar evento: {e}")
            return f"Erro ao criar evento: {str(e)}"

    @tool
    def _verificar_disponibilidade(data: str, hora_inicio: str = "08:00", hora_fim: str = "18:00") -> str:
        """
        Verifica horários livres em uma data.
        
        Args:
            data: Data para verificar (formato: YYYY-MM-DD)
            hora_inicio: Hora inicial do período (padrão: 08:00)
            hora_fim: Hora final do período (padrão: 18:00)
        """
        try:
            service = get_calendar_service()
            if not service:
                return "Google Calendar não configurado."
            
            start = datetime.fromisoformat(f"{data}T{hora_inicio}:00")
            end = datetime.fromisoformat(f"{data}T{hora_fim}:00")
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=start.isoformat() + 'Z',
                timeMax=end.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return f"Agenda livre em {data} das {hora_inicio} às {hora_fim}."
            
            ocupados = []
            for event in events:
                ev_start = event['start'].get('dateTime', '')
                ev_end = event['end'].get('dateTime', '')
                if ev_start and ev_end:
                    s = datetime.fromisoformat(ev_start.replace('Z', '+00:00'))
                    e = datetime.fromisoformat(ev_end.replace('Z', '+00:00'))
                    ocupados.append(f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}: {event['summary']}")
            
            return f"Horários ocupados em {data}:\n" + "\n".join(ocupados)
        except Exception as e:
            logger.error(f"[GCAL] Erro ao verificar disponibilidade: {e}")
            return f"Erro: {str(e)}"


google_calendar_tools = GoogleCalendarTools()

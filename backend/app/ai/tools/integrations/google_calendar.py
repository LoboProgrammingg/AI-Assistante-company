"""
Google Calendar - Integração com agenda do Google via OAuth por usuário.
Cada usuário conecta seu próprio calendário no dashboard.
Docs: https://developers.google.com/calendar/api
"""

import logging
from datetime import datetime, timedelta
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

class GoogleCalendarTools:
    """
    Tools para integração com Google Calendar via OAuth por usuário.

    IMPORTANTE: Estas tools verificam se o usuário tem o calendário conectado.
    O usuário precisa conectar sua conta Google no dashboard primeiro.
    """

    def __init__(self):
        pass

    @property
    def is_configured(self) -> bool:
        """OAuth está sempre disponível se configurado no servidor."""
        from app.config import settings
        return bool(settings.GOOGLE_OAUTH_CLIENT_ID)

    def get_tools(self) -> list:
        """Retorna tools disponíveis."""
        return [
            self._listar_eventos,
            self._criar_evento,
            self._verificar_disponibilidade,
        ]

    @tool
    def _listar_eventos(data: str = None, dias: int = 7) -> str:
        """
        Lista eventos da agenda Google do usuário.
        O usuário precisa ter conectado seu Google Calendar no dashboard.

        Args:
            data: Data inicial (formato: YYYY-MM-DD). Padrão: hoje
            dias: Número de dias a consultar (1-30)
        """
        return {
            "status": "pending_calendar_action",
            "action": "list_events",
            "params": {
                "data": data,
                "dias": min(dias, 30)
            },
            "message": "Para listar eventos, o usuário precisa conectar o Google Calendar no dashboard."
        }

    @tool
    def _criar_evento(
        titulo: str,
        data_hora: str,
        duracao_minutos: int = 60,
        descricao: str = "",
        participantes: str = "",
        adicionar_meet: bool = True
    ) -> str:
        """
        Cria um evento/reunião no Google Calendar do usuário COM convites por e-mail.
        
        IMPORTANTE - FLUXO DE CRIAÇÃO:
        1. Se o usuário NÃO informou participantes, PERGUNTE os e-mails antes de criar
        2. Participantes recebem convite por e-mail automaticamente
        3. Se adicionar_meet=True, um link do Google Meet é gerado
        
        O usuário precisa ter conectado seu Google Calendar nas Configurações.

        Args:
            titulo: Título do evento/reunião (obrigatório)
            data_hora: Data e hora no formato YYYY-MM-DD HH:MM (obrigatório)
            duracao_minutos: Duração em minutos (padrão: 60)
            descricao: Descrição ou pauta da reunião (opcional mas recomendado)
            participantes: E-MAILS dos participantes separados por vírgula (ex: "joao@email.com, maria@email.com")
            adicionar_meet: Se True, cria link do Google Meet automaticamente (padrão: True)
        
        Returns:
            Dict com status da ação e dados do evento
        """
        participantes_list = [e.strip() for e in participantes.split(',') if e.strip() and '@' in e] if participantes else []
        
        # Se não tem participantes, sinalizar para pedir
        needs_participants = len(participantes_list) == 0
        
        return {
            "status": "pending_calendar_action",
            "action": "create_event",
            "params": {
                "titulo": titulo,
                "data_hora": data_hora,
                "duracao_minutos": duracao_minutos,
                "descricao": descricao,
                "participantes": participantes_list,
                "adicionar_meet": adicionar_meet
            },
            "needs_participants": needs_participants,
            "message": f"Evento '{titulo}' agendado para {data_hora}." if participantes_list else f"Para enviar convites, preciso dos e-mails dos participantes."
        }

    @tool
    def _verificar_disponibilidade(data: str, hora_inicio: str = "08:00", hora_fim: str = "18:00") -> str:
        """
        Verifica horários livres na agenda do usuário.
        O usuário precisa ter conectado seu Google Calendar no dashboard.

        Args:
            data: Data para verificar (formato: YYYY-MM-DD)
            hora_inicio: Hora inicial do período (padrão: 08:00)
            hora_fim: Hora final do período (padrão: 18:00)
        """
        return {
            "status": "pending_calendar_action",
            "action": "check_availability",
            "params": {
                "data": data,
                "hora_inicio": hora_inicio,
                "hora_fim": hora_fim
            },
            "message": "Para verificar disponibilidade, o usuário precisa conectar o Google Calendar."
        }

google_calendar_tools = GoogleCalendarTools()

"""
Calendar Executor - Execução de ações do Google Calendar.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

logger = logging.getLogger(__name__)


class CalendarExecutor:
    """Executor de ações do Google Calendar."""
    
    @staticmethod
    def create_event(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Cria evento no Google Calendar."""
        try:
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo
            from app.services.google_calendar_service import GoogleCalendarService
            
            service = GoogleCalendarService(db)
            
            if not service.is_user_connected(user_id):
                return ExecutionResult(
                    success=False,
                    action_type="create_event",
                    response_template="⚠️ Conecte seu Google Calendar nas *Configurações*.",
                )
            
            tz = ZoneInfo("America/Sao_Paulo")
            
            titulo = params.get("titulo", params.get("title", "Reunião"))
            data_hora = params.get("data_hora", params.get("start_time", ""))
            duracao = params.get("duracao_minutos", params.get("duration", 60))
            participantes = params.get("participantes", params.get("attendees", []))
            
            try:
                start_time = datetime.strptime(data_hora, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            except ValueError:
                return ExecutionResult(success=False, action_type="create_event", error=f"Formato de data inválido: {data_hora}")
            
            end_time = start_time + timedelta(minutes=duracao)
            
            result = service.create_event(
                user_id=user_id, title=titulo, start_time=start_time, end_time=end_time,
                attendees=participantes, add_meet=True,
            )
            
            if result.get("success"):
                event = result.get("event", {})
                meet_link = event.get("hangoutLink", "")
                
                template = f"📅 *Evento criado:* {titulo}\n🕐 {start_time.strftime('%d/%m/%Y às %H:%M')}"
                if meet_link:
                    template += f"\n🔗 {meet_link}"
                
                return ExecutionResult(success=True, action_type="create_event", data=event, response_template=template)
            
            return ExecutionResult(success=False, action_type="create_event", error=result.get("error", "Erro ao criar evento"))
            
        except ImportError:
            return ExecutionResult(success=False, action_type="create_event", error="Serviço de Calendar não disponível")
        except Exception as e:
            logger.error(f"Erro ao criar evento: {e}")
            return ExecutionResult(success=False, action_type="create_event", error=str(e))
    
    @staticmethod
    def list_events(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Lista eventos do Google Calendar."""
        try:
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo
            from app.services.google_calendar_service import GoogleCalendarService
            
            service = GoogleCalendarService(db)
            
            if not service.is_user_connected(user_id):
                return ExecutionResult(success=False, action_type="list_events", response_template="⚠️ Conecte seu Google Calendar nas Configurações.")
            
            tz = ZoneInfo("America/Sao_Paulo")
            dias = params.get("dias", 7)
            time_max = datetime.now(tz) + timedelta(days=dias)
            
            result = service.list_events(user_id=user_id, max_results=10, time_max=time_max)
            
            if result.get("success"):
                events = result.get("events", [])
                
                if not events:
                    template = f"📅 Nenhum evento nos próximos {dias} dias."
                else:
                    lines = [f"📅 *Próximos eventos ({dias} dias):*\n"]
                    for e in events[:10]:
                        start = e.get("start", {}).get("dateTime", "")[:16]
                        title = e.get("summary", "Sem título")
                        lines.append(f"• {title} - {start}")
                    template = "\n".join(lines)
                
                return ExecutionResult(success=True, action_type="list_events", data={"events": events}, response_template=template)
            
            return ExecutionResult(success=False, action_type="list_events", error=result.get("error"))
        except Exception as e:
            logger.error(f"Erro ao listar eventos: {e}")
            return ExecutionResult(success=False, action_type="list_events", error=str(e))
    
    @staticmethod
    def check_availability(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Verifica disponibilidade no Calendar."""
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            from app.services.google_calendar_service import GoogleCalendarService
            
            service = GoogleCalendarService(db)
            
            if not service.is_user_connected(user_id):
                return ExecutionResult(success=False, action_type="check_availability", response_template="⚠️ Conecte seu Google Calendar nas Configurações.")
            
            tz = ZoneInfo("America/Sao_Paulo")
            data = params.get("data", "")
            hora_inicio = params.get("hora_inicio", "08:00")
            hora_fim = params.get("hora_fim", "18:00")
            
            start_time = datetime.strptime(f"{data} {hora_inicio}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            end_time = datetime.strptime(f"{data} {hora_fim}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            
            result = service.check_availability(user_id, start_time, end_time)
            
            if result.get("success"):
                is_free = result.get("is_free", False)
                template = "✅ Horário livre!" if is_free else "❌ Horário ocupado."
                return ExecutionResult(success=True, action_type="check_availability", data=result, response_template=template)
            
            return ExecutionResult(success=False, action_type="check_availability", error=result.get("error"))
        except Exception as e:
            logger.error(f"Erro ao verificar disponibilidade: {e}")
            return ExecutionResult(success=False, action_type="check_availability", error=str(e))

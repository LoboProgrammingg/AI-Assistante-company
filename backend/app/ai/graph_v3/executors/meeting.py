"""
Meeting Executor - Execução de ações de reuniões (banco local).
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

logger = logging.getLogger(__name__)


class MeetingExecutor:
    """Executor de ações de reuniões (banco local)."""
    
    @staticmethod
    def create(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Cria reunião no banco local."""
        from app.services.meeting_service import MeetingService
        
        try:
            service = MeetingService(db)
            
            meeting_data = {
                "title": params.get("titulo", params.get("title", "")),
                "scheduled_time": params.get("data_hora", params.get("scheduled_time", "")),
                "participants": params.get("participantes", params.get("participants", [])),
                "duration_minutes": params.get("duracao_minutos", 60),
            }
            
            service.create_from_entities(user_id, meeting_data)
            
            template = f"📅 Reunião *{meeting_data['title']}* agendada!"
            return ExecutionResult(success=True, action_type="create_meeting", data=meeting_data, response_template=template)
        except Exception as e:
            logger.error(f"Erro ao criar reunião: {e}")
            return ExecutionResult(success=False, action_type="create_meeting", error=str(e))
    
    @staticmethod
    def list_all(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Lista reuniões."""
        from app.services.meeting_service import MeetingService
        
        try:
            service = MeetingService(db)
            meetings, total = service.list_by_user(user_id, limit=10)
            
            if not meetings:
                template = "📅 Nenhuma reunião agendada."
            else:
                lines = ["📅 *Suas reuniões:*\n"]
                for m in meetings[:10]:
                    time_str = m.scheduled_time.strftime("%d/%m %H:%M") if m.scheduled_time else ""
                    lines.append(f"• {m.title} - {time_str}")
                template = "\n".join(lines)
            
            return ExecutionResult(success=True, action_type="list_meetings", data={"meetings": meetings}, response_template=template)
        except Exception as e:
            logger.error(f"Erro ao listar reuniões: {e}")
            return ExecutionResult(success=False, action_type="list_meetings", error=str(e))
    
    @staticmethod
    def summarize_transcription(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Resume transcrição - precisa de LLM."""
        return ExecutionResult(
            success=True,
            action_type="summarize_transcription",
            data={"transcription": params.get("transcricao", params.get("transcription", "")), "needs_llm": True},
            response_template=None,
        )

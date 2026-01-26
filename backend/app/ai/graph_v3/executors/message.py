"""
Message Executor - Execução de ações de mensagens agendadas.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

logger = logging.getLogger(__name__)


class MessageExecutor:
    """Executor de ações de mensagens agendadas."""
    
    @staticmethod
    def schedule(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Agenda mensagem."""
        from app.services.scheduled_message_service import ScheduledMessageService
        
        try:
            service = ScheduledMessageService(db)
            msg_data = {
                "message": params.get("mensagem", params.get("message", "")),
                "scheduled_time": params.get("data_hora", params.get("scheduled_time", "")),
                "recipient_name": params.get("destinatario_nome", ""),
                "recipient_phone": params.get("destinatario_telefone", ""),
                "group_name": params.get("grupo", ""),
            }
            
            scheduled = service.create_from_entities(user_id, msg_data)
            template = f"📨 Mensagem agendada para {scheduled.scheduled_time.strftime('%d/%m às %H:%M')}!"
            
            return ExecutionResult(success=True, action_type="schedule_message", data=msg_data, response_template=template)
        except Exception as e:
            logger.error(f"Erro ao agendar mensagem: {e}")
            return ExecutionResult(success=False, action_type="schedule_message", error=str(e))
    
    @staticmethod
    def list_all(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Lista mensagens agendadas."""
        from app.services.scheduled_message_service import ScheduledMessageService
        
        try:
            service = ScheduledMessageService(db)
            messages = service.list(user_id, status=params.get("status"))
            
            if not messages:
                template = "📭 Nenhuma mensagem agendada."
            else:
                lines = ["📨 *Mensagens agendadas:*\n"]
                for m in messages[:10]:
                    lines.append(f"• {m.get('recipient', 'Destinatário')} - {m.get('scheduled_time', '')[:16]}")
                template = "\n".join(lines)
            
            return ExecutionResult(success=True, action_type="list_scheduled_messages", data={"messages": messages}, response_template=template)
        except Exception as e:
            logger.error(f"Erro ao listar mensagens: {e}")
            return ExecutionResult(success=False, action_type="list_scheduled_messages", error=str(e))

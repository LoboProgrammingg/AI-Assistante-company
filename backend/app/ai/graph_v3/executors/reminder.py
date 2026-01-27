"""
Reminder Executor - Execução de ações de lembretes.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

logger = logging.getLogger(__name__)


class ReminderExecutor:
    """Executor de ações de lembretes."""

    @staticmethod
    def create(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Cria lembrete."""
        from app.services.reminder_service import ReminderService

        try:
            service = ReminderService(db)

            reminder_data = {
                "title": params.get("titulo", params.get("title", "")),
                "scheduled_time": params.get("horario", params.get("scheduled_time", "")),
                "description": params.get("descricao", params.get("description", "")),
            }

            service.create_from_entities(user_id, reminder_data)

            template = f"⏰ Lembrete criado: *{reminder_data['title']}*\n📅 {reminder_data['scheduled_time']}"

            return ExecutionResult(
                success=True,
                action_type="create_reminder",
                data={"reminder": reminder_data},
                response_template=template,
            )
        except Exception as e:
            logger.error(f"Erro ao criar lembrete: {e}")
            return ExecutionResult(success=False, action_type="create_reminder", error=str(e))

    @staticmethod
    def list_all(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Lista lembretes."""
        from app.services.reminder_service import ReminderService

        try:
            service = ReminderService(db)
            reminders, total = service.list_by_user(user_id, status="active", limit=10)

            if not reminders:
                template = "📭 Você não tem lembretes pendentes."
            else:
                lines = ["⏰ *Seus lembretes:*\n"]
                for r in reminders[:10]:
                    time_str = r.scheduled_time.strftime("%d/%m %H:%M") if r.scheduled_time else ""
                    lines.append(f"• {r.title} - {time_str}")

                if total > 10:
                    lines.append(f"\n_+{total - 10} lembretes_")

                template = "\n".join(lines)

            return ExecutionResult(
                success=True,
                action_type="list_reminders",
                data={"reminders": [{"title": r.title, "time": str(r.scheduled_time)} for r in reminders]},
                response_template=template,
            )
        except Exception as e:
            logger.error(f"Erro ao listar lembretes: {e}")
            return ExecutionResult(success=False, action_type="list_reminders", error=str(e))

    @staticmethod
    def delete(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Deleta lembrete."""
        from app.services.reminder_service import ReminderService

        try:
            service = ReminderService(db)
            result = service.delete_by_filters(user_id, params)

            count = result.get("deleted_count", 0)
            template = f"🗑️ {count} lembrete(s) deletado(s)." if count > 0 else "❌ Nenhum lembrete encontrado."

            return ExecutionResult(
                success=count > 0, action_type="delete_reminder", data=result, response_template=template
            )
        except Exception as e:
            return ExecutionResult(success=False, action_type="delete_reminder", error=str(e))

    @staticmethod
    def update(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Atualiza lembrete."""
        from app.services.reminder_service import ReminderService

        try:
            service = ReminderService(db)
            filters = {"titulo": params.get("titulo_busca", params.get("titulo", ""))}
            updates = {}

            if params.get("novo_titulo"):
                updates["title"] = params["novo_titulo"]
            if params.get("nova_data_hora"):
                updates["scheduled_time"] = params["nova_data_hora"]

            result = service.update_by_filters(user_id, filters, updates)

            if result.get("success"):
                return ExecutionResult(
                    success=True, action_type="update_reminder", data=result, response_template="✏️ Lembrete atualizado!"
                )

            return ExecutionResult(
                success=False, action_type="update_reminder", error=result.get("error", "Não encontrado")
            )
        except Exception as e:
            return ExecutionResult(success=False, action_type="update_reminder", error=str(e))

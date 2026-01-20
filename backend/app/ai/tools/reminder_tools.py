"""
Tools de Lembretes com Pydantic Schemas para LangGraph.
"""

import logging
from datetime import datetime
from typing import List, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CriarLembreteSchema(BaseModel):
    """Schema para criar lembrete."""

    titulo: str = Field(
        description="Título ou descrição do lembrete (ex: 'Reunião com cliente')", min_length=2, max_length=200
    )
    data_hora: str = Field(
        description="Data e hora do lembrete (formato: YYYY-MM-DD HH:MM ou descrição como 'amanhã às 10h')"
    )
    recorrencia: Optional[Literal["none", "daily", "weekly", "monthly"]] = Field(
        description="Tipo de recorrência: none, daily, weekly ou monthly", default="none"
    )
    prioridade: Optional[Literal["low", "medium", "high"]] = Field(
        description="Prioridade do lembrete", default="medium"
    )


class ListarLembretesSchema(BaseModel):
    """Schema para listar lembretes."""

    periodo: Literal["hoje", "amanha", "semana", "todos"] = Field(
        description="Período: hoje, amanha, semana ou todos", default="semana"
    )
    apenas_pendentes: bool = Field(description="Se True, mostra apenas lembretes pendentes", default=True)


class DeletarLembreteSchema(BaseModel):
    """Schema para deletar lembrete."""

    lembrete_id: Optional[int] = Field(description="ID do lembrete a deletar", default=None)
    titulo: Optional[str] = Field(description="Título parcial para encontrar o lembrete", default=None)


@tool(args_schema=CriarLembreteSchema)
def criar_lembrete(titulo: str, data_hora: str, recorrencia: str = "none", prioridade: str = "medium") -> dict:
    """
    Cria um novo lembrete para o usuário.
    Use quando o usuário quiser ser lembrado de algo.
    """
    return {
        "action": "create_reminder",
        "reminder": {"title": titulo, "scheduled_time": data_hora, "recurrence": recorrencia, "priority": prioridade},
        "status": "pending_execution",
    }


@tool(args_schema=ListarLembretesSchema)
def listar_lembretes(periodo: str = "semana", apenas_pendentes: bool = True) -> dict:
    """
    Lista os lembretes do usuário.
    Use quando o usuário quiser ver seus lembretes.
    """
    return {
        "action": "list_reminders",
        "filters": {"periodo": periodo, "apenas_pendentes": apenas_pendentes},
        "status": "pending_execution",
    }


@tool(args_schema=DeletarLembreteSchema)
def deletar_lembrete(lembrete_id: Optional[int] = None, titulo: Optional[str] = None) -> dict:
    """
    Deleta um lembrete existente.
    Use quando o usuário quiser remover um lembrete.
    """
    return {
        "action": "delete_reminder",
        "filters": {"id": lembrete_id, "titulo": titulo},
        "status": "pending_execution",
    }


class ReminderTools:
    """Agregador de tools de lembretes."""

    @staticmethod
    def get_all_tools() -> List:
        return [criar_lembrete, listar_lembretes, deletar_lembrete]

    @staticmethod
    def execute_tool_result(result: dict, db, user_id: int) -> dict:
        """Executa o resultado de uma tool no banco."""
        from app.services.reminder_service import ReminderService

        action = result.get("action")
        service = ReminderService(db)

        if action == "create_reminder":
            reminder_data = result.get("reminder", {})
            try:
                created = service.create_from_entities(user_id, reminder_data)
                return {
                    "success": True,
                    "message": f"Lembrete '{reminder_data['title']}' criado!",
                    "data": reminder_data,
                }
            except Exception as e:
                logger.error(f"Erro ao criar lembrete: {e}")
                return {"success": False, "error": str(e)}

        elif action == "list_reminders":
            filters = result.get("filters", {})
            try:
                reminders = service.get_upcoming(user_id, filters.get("periodo", "semana"))
                return {"success": True, "data": reminders}
            except Exception as e:
                logger.error(f"Erro ao listar lembretes: {e}")
                return {"success": False, "error": str(e)}

        elif action == "delete_reminder":
            filters = result.get("filters", {})
            try:
                deleted = service.delete_by_filters(user_id, filters)
                return {"success": True, "message": "Lembrete deletado!"}
            except Exception as e:
                logger.error(f"Erro ao deletar lembrete: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Ação desconhecida"}

"""
Tools de Lembretes com Pydantic Schemas para LangGraph.
"""

import logging
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

    titulo: str = Field(description="Título ou termo para encontrar o(s) lembrete(s) a deletar (ex: 'reunião', 'médico')")


class AtualizarLembreteSchema(BaseModel):
    """Schema para atualizar lembrete."""

    titulo_busca: str = Field(description="Título atual do lembrete para encontrá-lo")
    novo_titulo: Optional[str] = Field(description="Novo título do lembrete", default=None)
    nova_data_hora: Optional[str] = Field(description="Nova data/hora (formato: YYYY-MM-DD HH:MM)", default=None)


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
def deletar_lembrete(titulo: str) -> dict:
    """
    Deleta lembrete(s) por título.
    Use quando o usuário pedir para remover/deletar um lembrete.
    Exemplos: "delete o lembrete da reunião", "remove o lembrete do médico"
    """
    return {
        "action": "delete_reminder",
        "filters": {"titulo": titulo},
        "status": "pending_execution",
    }


@tool(args_schema=AtualizarLembreteSchema)
def atualizar_lembrete(
    titulo_busca: str,
    novo_titulo: Optional[str] = None,
    nova_data_hora: Optional[str] = None,
) -> dict:
    """
    Atualiza um lembrete existente.
    Use quando o usuário quiser alterar título ou horário de um lembrete.
    Exemplos: "mude a reunião para 18h", "altere o horário do médico para amanhã"
    """
    updates = {}
    if novo_titulo:
        updates["title"] = novo_titulo
    if nova_data_hora:
        updates["scheduled_time"] = nova_data_hora
    
    return {
        "action": "update_reminder",
        "filters": {"titulo": titulo_busca},
        "updates": updates,
        "status": "pending_execution",
    }


class ReminderTools:
    """Agregador de tools de lembretes."""

    @staticmethod
    def get_all_tools() -> List:
        return [criar_lembrete, listar_lembretes, deletar_lembrete, atualizar_lembrete]

    @staticmethod
    def execute_tool_result(result: dict, db, user_id: int) -> dict:
        """Executa o resultado de uma tool no banco."""
        from app.services.reminder_service import ReminderService

        action = result.get("action")
        service = ReminderService(db)

        if action == "create_reminder":
            reminder_data = result.get("reminder", {})
            try:
                service.create_from_entities(user_id, reminder_data)
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
                delete_result = service.delete_by_filters(user_id, filters)
                count = delete_result.get("deleted_count", 0)
                items = delete_result.get("deleted_items", [])
                if count > 0:
                    return {"success": True, "message": f"{count} lembrete(s) deletado(s): {', '.join(items)}"}
                return {"success": False, "message": "Nenhum lembrete encontrado com esse título."}
            except Exception as e:
                logger.error(f"Erro ao deletar lembrete: {e}")
                return {"success": False, "error": str(e)}

        elif action == "update_reminder":
            filters = result.get("filters", {})
            updates = result.get("updates", {})
            try:
                update_result = service.update_by_filters(user_id, filters, updates)
                if update_result.get("success"):
                    return {"success": True, "message": f"Lembrete atualizado: {update_result.get('message', '')}"}
                return {"success": False, "message": update_result.get("error", "Lembrete não encontrado")}
            except Exception as e:
                logger.error(f"Erro ao atualizar lembrete: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Ação desconhecida"}

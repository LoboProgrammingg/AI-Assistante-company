"""
Todoist Tools - Integração com Todoist para LangGraph.

Tools para criar, listar, atualizar e deletar tarefas no Todoist,
além de verificar alertas de tarefas próximas do prazo.

Docs: https://developer.todoist.com/rest/v2/
"""

import logging
from typing import List, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CriarTarefaTodoistSchema(BaseModel):
    """Schema para criar tarefa no Todoist."""

    titulo: str = Field(
        description="Título da tarefa (ex: 'Estudar Python', 'Reunião com cliente')",
        min_length=2,
        max_length=500,
    )
    descricao: Optional[str] = Field(
        description="Descrição detalhada da tarefa (opcional)",
        default=None,
    )
    prazo: Optional[str] = Field(
        description="Prazo em linguagem natural (ex: 'amanhã às 10h', 'sexta-feira', '25/01 às 14:00')",
        default=None,
    )
    prioridade: Optional[Literal[1, 2, 3, 4]] = Field(
        description="Prioridade: 1 (normal), 2 (média), 3 (alta), 4 (urgente)",
        default=1,
    )
    labels: Optional[str] = Field(
        description="Labels separadas por vírgula (ex: 'trabalho, urgente')",
        default=None,
    )


class ListarTarefasTodoistSchema(BaseModel):
    """Schema para listar tarefas do Todoist."""

    filtro: Optional[str] = Field(
        description="Filtro do Todoist: 'today' (hoje), 'tomorrow' (amanhã), 'overdue' (atrasadas), 'p1' (prioridade 1), 'all' (todas)",
        default="today",
    )


class ConcluirTarefaTodoistSchema(BaseModel):
    """Schema para concluir tarefa no Todoist."""

    titulo_ou_id: str = Field(
        description="Título parcial ou ID da tarefa a concluir (ex: 'estudar', 'reunião')",
    )


class AtualizarTarefaTodoistSchema(BaseModel):
    """Schema para atualizar tarefa no Todoist."""

    titulo_busca: str = Field(
        description="Título parcial da tarefa para encontrá-la",
    )
    novo_titulo: Optional[str] = Field(
        description="Novo título da tarefa",
        default=None,
    )
    novo_prazo: Optional[str] = Field(
        description="Novo prazo em linguagem natural",
        default=None,
    )
    nova_prioridade: Optional[Literal[1, 2, 3, 4]] = Field(
        description="Nova prioridade (1-4)",
        default=None,
    )


class DeletarTarefaTodoistSchema(BaseModel):
    """Schema para deletar tarefa do Todoist."""

    titulo_ou_id: str = Field(
        description="Título parcial ou ID da tarefa a deletar",
    )


class VerificarAlertasTodoistSchema(BaseModel):
    """Schema para verificar alertas de tarefas próximas do prazo."""

    pass  # Sem parâmetros necessários


@tool(args_schema=CriarTarefaTodoistSchema)
def criar_tarefa_todoist(
    titulo: str,
    descricao: str = None,
    prazo: str = None,
    prioridade: int = 1,
    labels: str = None,
) -> dict:
    """
    Cria uma nova tarefa no Todoist do usuário.
    Use quando o usuário quiser adicionar uma tarefa, to-do, ou item de lista.
    Exemplos: "adicione no todoist estudar python amanhã", "crie uma tarefa para reunião"
    """
    labels_list = [l.strip() for l in labels.split(",")] if labels else None
    
    return {
        "action": "create_todoist_task",
        "task": {
            "content": titulo,
            "description": descricao,
            "due_string": prazo,
            "priority": prioridade,
            "labels": labels_list,
        },
        "status": "pending_execution",
    }


@tool(args_schema=ListarTarefasTodoistSchema)
def listar_tarefas_todoist(filtro: str = "today") -> dict:
    """
    Lista as tarefas do Todoist do usuário.
    Use quando o usuário quiser ver suas tarefas, to-dos, ou pendências.
    Exemplos: "quais são minhas tarefas de hoje?", "me mostre as tarefas atrasadas"
    """
    # Mapear filtros em português para filtros do Todoist
    filter_map = {
        "hoje": "today",
        "amanha": "tomorrow",
        "amanhã": "tomorrow",
        "atrasadas": "overdue",
        "todas": "all",
        "today": "today",
        "tomorrow": "tomorrow",
        "overdue": "overdue",
        "all": "all",
        "p1": "p1",
        "p2": "p2",
        "p3": "p3",
        "p4": "p4",
    }
    
    todoist_filter = filter_map.get(filtro.lower(), "today")
    
    return {
        "action": "list_todoist_tasks",
        "filters": {"filter": todoist_filter},
        "status": "pending_execution",
    }


@tool(args_schema=ConcluirTarefaTodoistSchema)
def concluir_tarefa_todoist(titulo_ou_id: str) -> dict:
    """
    Marca uma tarefa como concluída no Todoist.
    Use quando o usuário disser que completou/terminou/fez uma tarefa.
    Exemplos: "terminei de estudar python", "conclua a tarefa da reunião"
    """
    return {
        "action": "complete_todoist_task",
        "filters": {"titulo_ou_id": titulo_ou_id},
        "status": "pending_execution",
    }


@tool(args_schema=AtualizarTarefaTodoistSchema)
def atualizar_tarefa_todoist(
    titulo_busca: str,
    novo_titulo: str = None,
    novo_prazo: str = None,
    nova_prioridade: int = None,
) -> dict:
    """
    Atualiza uma tarefa existente no Todoist.
    Use quando o usuário quiser alterar título, prazo ou prioridade de uma tarefa.
    Exemplos: "mude o prazo da tarefa estudar para sexta", "aumente a prioridade da reunião"
    """
    updates = {}
    if novo_titulo:
        updates["content"] = novo_titulo
    if novo_prazo:
        updates["due_string"] = novo_prazo
    if nova_prioridade:
        updates["priority"] = nova_prioridade
    
    return {
        "action": "update_todoist_task",
        "filters": {"titulo": titulo_busca},
        "updates": updates,
        "status": "pending_execution",
    }


@tool(args_schema=DeletarTarefaTodoistSchema)
def deletar_tarefa_todoist(titulo_ou_id: str) -> dict:
    """
    Deleta uma tarefa do Todoist.
    Use quando o usuário quiser remover/deletar/excluir uma tarefa.
    Exemplos: "delete a tarefa de estudar", "remova a reunião do todoist"
    """
    return {
        "action": "delete_todoist_task",
        "filters": {"titulo_ou_id": titulo_ou_id},
        "status": "pending_execution",
    }


@tool(args_schema=VerificarAlertasTodoistSchema)
def verificar_alertas_todoist() -> dict:
    """
    Verifica se há tarefas do Todoist próximas do prazo (zona de alerta).
    Use quando o usuário perguntar sobre tarefas urgentes ou próximas de vencer.
    Exemplos: "tenho alguma tarefa urgente?", "quais tarefas vencem em breve?"
    """
    return {
        "action": "check_todoist_alerts",
        "status": "pending_execution",
    }


class TodoistTools:
    """Agregador de tools do Todoist."""

    @staticmethod
    def get_tools() -> List:
        """Retorna todas as tools do Todoist."""
        return [
            criar_tarefa_todoist,
            listar_tarefas_todoist,
            concluir_tarefa_todoist,
            atualizar_tarefa_todoist,
            deletar_tarefa_todoist,
            verificar_alertas_todoist,
        ]

    @staticmethod
    async def execute_tool_result(result: dict, user_name: str = None) -> dict:
        """
        Executa o resultado de uma tool no Todoist.
        
        Args:
            result: Resultado da tool com action e parâmetros
            user_name: Nome do usuário para mensagens personalizadas
            
        Returns:
            Dict com sucesso/erro e dados
        """
        from app.services.todoist_service import get_todoist_service

        action = result.get("action")
        service = get_todoist_service()

        if not service.is_configured:
            return {
                "success": False,
                "error": "Todoist não configurado. Adicione TODOIST_API_KEY no servidor.",
            }

        try:
            if action == "create_todoist_task":
                task_data = result.get("task", {})
                task = await service.create_task(
                    content=task_data.get("content"),
                    description=task_data.get("description"),
                    due_string=task_data.get("due_string"),
                    priority=task_data.get("priority", 1),
                    labels=task_data.get("labels"),
                )
                if task:
                    return {
                        "success": True,
                        "message": f"✅ Tarefa '{task['content']}' criada no Todoist!",
                        "data": task,
                    }
                return {"success": False, "error": "Erro ao criar tarefa no Todoist"}

            elif action == "list_todoist_tasks":
                filters = result.get("filters", {})
                filter_str = filters.get("filter", "today")
                
                # "all" não é um filtro válido do Todoist
                if filter_str == "all":
                    filter_str = None
                
                tasks = await service.get_tasks(filter_str=filter_str)
                
                if not tasks:
                    return {
                        "success": True,
                        "message": "📋 Nenhuma tarefa encontrada com esse filtro.",
                        "data": [],
                    }
                
                return {
                    "success": True,
                    "message": f"📋 {len(tasks)} tarefa(s) encontrada(s)",
                    "data": tasks,
                }

            elif action == "complete_todoist_task":
                filters = result.get("filters", {})
                titulo_ou_id = filters.get("titulo_ou_id", "")
                
                # Buscar tarefa pelo título
                tasks = await service.get_tasks()
                matching_task = None
                
                for task in tasks:
                    if titulo_ou_id.lower() in task["content"].lower() or task["id"] == titulo_ou_id:
                        matching_task = task
                        break
                
                if not matching_task:
                    return {
                        "success": False,
                        "error": f"Tarefa '{titulo_ou_id}' não encontrada",
                    }
                
                success = await service.complete_task(matching_task["id"])
                if success:
                    return {
                        "success": True,
                        "message": f"✅ Tarefa '{matching_task['content']}' concluída!",
                    }
                return {"success": False, "error": "Erro ao concluir tarefa"}

            elif action == "update_todoist_task":
                filters = result.get("filters", {})
                updates = result.get("updates", {})
                titulo = filters.get("titulo", "")
                
                # Buscar tarefa pelo título
                tasks = await service.get_tasks()
                matching_task = None
                
                for task in tasks:
                    if titulo.lower() in task["content"].lower():
                        matching_task = task
                        break
                
                if not matching_task:
                    return {
                        "success": False,
                        "error": f"Tarefa '{titulo}' não encontrada",
                    }
                
                success = await service.update_task(
                    task_id=matching_task["id"],
                    content=updates.get("content"),
                    due_string=updates.get("due_string"),
                    priority=updates.get("priority"),
                )
                
                if success:
                    return {
                        "success": True,
                        "message": f"✅ Tarefa '{matching_task['content']}' atualizada!",
                    }
                return {"success": False, "error": "Erro ao atualizar tarefa"}

            elif action == "delete_todoist_task":
                filters = result.get("filters", {})
                titulo_ou_id = filters.get("titulo_ou_id", "")
                
                # Buscar tarefa pelo título
                tasks = await service.get_tasks()
                matching_task = None
                
                for task in tasks:
                    if titulo_ou_id.lower() in task["content"].lower() or task["id"] == titulo_ou_id:
                        matching_task = task
                        break
                
                if not matching_task:
                    return {
                        "success": False,
                        "error": f"Tarefa '{titulo_ou_id}' não encontrada",
                    }
                
                success = await service.delete_task(matching_task["id"])
                if success:
                    return {
                        "success": True,
                        "message": f"🗑️ Tarefa '{matching_task['content']}' deletada!",
                    }
                return {"success": False, "error": "Erro ao deletar tarefa"}

            elif action == "check_todoist_alerts":
                alerts = await service.check_deadlines(user_name=user_name)
                
                if not alerts:
                    return {
                        "success": True,
                        "message": "✅ Nenhuma tarefa urgente no momento!",
                        "data": [],
                    }
                
                return {
                    "success": True,
                    "message": f"⚠️ {len(alerts)} tarefa(s) próxima(s) do prazo!",
                    "data": alerts,
                }

            return {"success": False, "error": f"Ação desconhecida: {action}"}

        except Exception as e:
            logger.error(f"❌ Erro ao executar tool Todoist: {e}")
            return {"success": False, "error": str(e)}


# Instância singleton
todoist_tools = TodoistTools()

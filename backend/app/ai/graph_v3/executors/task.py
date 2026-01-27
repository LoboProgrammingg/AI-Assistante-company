"""
Task Executor - Execução de ações do Gerenciador de Tarefas.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

logger = logging.getLogger(__name__)


class TaskExecutor:
    """Executor de ações de Tarefas."""
    
    @staticmethod
    def create(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Cria uma nova tarefa."""
        try:
            from app.services.task_service import TaskService
            
            service = TaskService(db)
            task = service.create_from_entities(user_id, params)
            
            priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "urgent": "🔴"}
            emoji = priority_emoji.get(task.priority.value, "📋")
            
            template = f"{emoji} *Tarefa criada!*\n\n📝 {task.title}"
            if task.due_date:
                template += f"\n📅 {task.due_date.strftime('%d/%m/%Y %H:%M')}"
            if task.project:
                template += f"\n📁 Projeto: {task.project.name}"
            
            return ExecutionResult(
                success=True,
                action_type="create_task",
                data={"task_id": task.id, "title": task.title},
                response_template=template,
            )
        except Exception as e:
            logger.error(f"Erro ao criar tarefa: {e}")
            return ExecutionResult(success=False, action_type="create_task", error=str(e))
    
    @staticmethod
    def list_all(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Lista tarefas do usuário."""
        try:
            from app.services.task_service import TaskService
            from app.models import TaskStatus, TaskPriority
            
            service = TaskService(db)
            
            # Filtros opcionais
            status_str = params.get("status")
            priority_str = params.get("priority", params.get("prioridade"))
            project_id = params.get("project_id")
            
            status = TaskStatus(status_str) if status_str else None
            priority = TaskPriority(priority_str) if priority_str else None
            
            tasks = service.list_tasks(
                user_id=user_id,
                status=status,
                priority=priority,
                project_id=project_id,
                limit=20,
            )
            
            if not tasks:
                return ExecutionResult(
                    success=True,
                    action_type="list_tasks",
                    data={"tasks": [], "count": 0},
                    response_template="📋 Você não tem tarefas pendentes.",
                )
            
            priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "urgent": "🔴"}
            
            lines = ["📋 *Suas tarefas:*\n"]
            for t in tasks[:10]:
                emoji = priority_emoji.get(t.priority.value, "📋")
                due = f" - {t.due_date.strftime('%d/%m')}" if t.due_date else ""
                overdue = " ⚠️" if t.is_overdue else ""
                lines.append(f"{emoji} {t.title}{due}{overdue}")
            
            if len(tasks) > 10:
                lines.append(f"\n_+{len(tasks) - 10} tarefas_")
            
            return ExecutionResult(
                success=True,
                action_type="list_tasks",
                data={"tasks": [{"id": t.id, "title": t.title, "status": t.status.value} for t in tasks], "count": len(tasks)},
                response_template="\n".join(lines),
            )
        except Exception as e:
            logger.error(f"Erro ao listar tarefas: {e}")
            return ExecutionResult(success=False, action_type="list_tasks", error=str(e))
    
    @staticmethod
    def complete(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Marca tarefa como concluída."""
        try:
            from app.services.task_service import TaskService
            
            service = TaskService(db)
            task_id = params.get("task_id", params.get("id"))
            title = params.get("title", params.get("titulo"))
            
            # Se não tem ID, tentar buscar por título
            if not task_id and title:
                tasks = service.list_tasks(user_id=user_id, limit=50)
                for t in tasks:
                    if title.lower() in t.title.lower():
                        task_id = t.id
                        break
            
            if not task_id:
                return ExecutionResult(
                    success=False,
                    action_type="complete_task",
                    error="Não encontrei essa tarefa. Qual tarefa você quer completar?",
                )
            
            task = service.complete_task(user_id, task_id)
            if not task:
                return ExecutionResult(success=False, action_type="complete_task", error="Tarefa não encontrada")
            
            return ExecutionResult(
                success=True,
                action_type="complete_task",
                data={"task_id": task.id},
                response_template=f"✅ Tarefa *{task.title}* concluída! 🎉",
            )
        except Exception as e:
            logger.error(f"Erro ao completar tarefa: {e}")
            return ExecutionResult(success=False, action_type="complete_task", error=str(e))
    
    @staticmethod
    def delete(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Remove uma tarefa."""
        try:
            from app.services.task_service import TaskService
            
            service = TaskService(db)
            task_id = params.get("task_id", params.get("id"))
            title = params.get("title", params.get("titulo"))
            
            # Se não tem ID, tentar buscar por título
            if not task_id and title:
                tasks = service.list_tasks(user_id=user_id, limit=50)
                for t in tasks:
                    if title.lower() in t.title.lower():
                        task_id = t.id
                        title = t.title
                        break
            
            if not task_id:
                return ExecutionResult(
                    success=False,
                    action_type="delete_task",
                    error="Não encontrei essa tarefa.",
                )
            
            if service.delete_task(user_id, task_id):
                return ExecutionResult(
                    success=True,
                    action_type="delete_task",
                    data={"task_id": task_id},
                    response_template=f"🗑️ Tarefa removida!",
                )
            
            return ExecutionResult(success=False, action_type="delete_task", error="Tarefa não encontrada")
        except Exception as e:
            logger.error(f"Erro ao remover tarefa: {e}")
            return ExecutionResult(success=False, action_type="delete_task", error=str(e))
    
    @staticmethod
    def get_summary(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Retorna resumo das tarefas."""
        try:
            from app.services.task_service import TaskService
            
            service = TaskService(db)
            summary = service.get_summary(user_id)
            
            lines = [
                "📊 *Resumo das suas tarefas:*\n",
                f"📋 Total: {summary['total']}",
                f"📝 A fazer: {summary['by_status']['todo']}",
                f"🔄 Em progresso: {summary['by_status']['in_progress']}",
                f"✅ Concluídas: {summary['by_status']['done']}",
            ]
            
            if summary['overdue'] > 0:
                lines.append(f"\n⚠️ *{summary['overdue']} tarefa(s) atrasada(s)!*")
            
            if summary['due_today'] > 0:
                lines.append(f"📅 {summary['due_today']} tarefa(s) para hoje")
            
            return ExecutionResult(
                success=True,
                action_type="task_summary",
                data=summary,
                response_template="\n".join(lines),
            )
        except Exception as e:
            logger.error(f"Erro ao obter resumo: {e}")
            return ExecutionResult(success=False, action_type="task_summary", error=str(e))

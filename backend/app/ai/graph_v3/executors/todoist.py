"""
Todoist Executor - Execução de ações do Todoist.
"""

import asyncio
import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

logger = logging.getLogger(__name__)


class TodoistExecutor:
    """Executor de ações do Todoist."""
    
    @staticmethod
    def _run_async(coro):
        """Executa coroutine de forma síncrona."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    @staticmethod
    def create_task(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Cria tarefa no Todoist."""
        try:
            from app.services.todoist_service import get_todoist_service
            
            service = get_todoist_service()
            
            content = params.get("content", params.get("titulo", ""))
            due_string = params.get("due_string", params.get("data", ""))
            priority = params.get("priority", 1)
            
            task = TodoistExecutor._run_async(service.create_task(
                content=content, due_string=due_string, priority=priority,
            ))
            
            if task:
                template = f"✅ Tarefa criada: *{content}*"
                if due_string:
                    template += f"\n📅 {due_string}"
                return ExecutionResult(success=True, action_type="create_todoist_task", data={"task": task}, response_template=template)
            
            return ExecutionResult(success=False, action_type="create_todoist_task", error="Erro ao criar tarefa")
        except Exception as e:
            logger.error(f"Erro ao criar tarefa Todoist: {e}")
            return ExecutionResult(success=False, action_type="create_todoist_task", error=str(e))
    
    @staticmethod
    def list_tasks(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Lista tarefas do Todoist."""
        try:
            from app.services.todoist_service import get_todoist_service
            
            service = get_todoist_service()
            filter_str = params.get("filter", "today")
            
            tasks = TodoistExecutor._run_async(service.get_tasks(filter_str=filter_str))
            
            if not tasks:
                template = "📭 Nenhuma tarefa encontrada."
            else:
                lines = ["📋 *Suas tarefas:*\n"]
                for t in tasks[:10]:
                    due = t.get("due", {}).get("string", "") if t.get("due") else ""
                    due_text = f" ({due})" if due else ""
                    lines.append(f"• {t['content']}{due_text}")
                template = "\n".join(lines)
            
            return ExecutionResult(success=True, action_type="list_todoist_tasks", data={"tasks": tasks}, response_template=template)
        except Exception as e:
            logger.error(f"Erro ao listar tarefas Todoist: {e}")
            return ExecutionResult(success=False, action_type="list_todoist_tasks", error=str(e))
    
    @staticmethod
    def complete_task(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Conclui tarefa no Todoist."""
        try:
            from app.services.todoist_service import get_todoist_service
            
            service = get_todoist_service()
            titulo_ou_id = params.get("titulo_ou_id", "")
            
            tasks = TodoistExecutor._run_async(service.get_tasks())
            
            matching_task = None
            for task in tasks:
                if titulo_ou_id.lower() in task["content"].lower() or task["id"] == titulo_ou_id:
                    matching_task = task
                    break
            
            if matching_task:
                success = TodoistExecutor._run_async(service.complete_task(matching_task["id"]))
                if success:
                    return ExecutionResult(success=True, action_type="complete_todoist_task",
                        response_template=f"✅ Tarefa *{matching_task['content']}* concluída!")
            
            return ExecutionResult(success=False, action_type="complete_todoist_task", error="Tarefa não encontrada")
        except Exception as e:
            return ExecutionResult(success=False, action_type="complete_todoist_task", error=str(e))
    
    @staticmethod
    def update_task(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Atualiza tarefa no Todoist."""
        try:
            from app.services.todoist_service import get_todoist_service
            
            service = get_todoist_service()
            titulo = params.get("titulo", params.get("titulo_busca", ""))
            updates = params.get("updates", {})
            
            tasks = TodoistExecutor._run_async(service.get_tasks())
            
            matching_task = None
            for task in tasks:
                if titulo.lower() in task["content"].lower():
                    matching_task = task
                    break
            
            if matching_task:
                success = TodoistExecutor._run_async(service.update_task(
                    task_id=matching_task["id"],
                    content=updates.get("content"),
                    due_string=updates.get("due_string"),
                    priority=updates.get("priority"),
                ))
                if success:
                    return ExecutionResult(success=True, action_type="update_todoist_task",
                        response_template=f"✏️ Tarefa *{matching_task['content']}* atualizada!")
            
            return ExecutionResult(success=False, action_type="update_todoist_task", error="Tarefa não encontrada")
        except Exception as e:
            return ExecutionResult(success=False, action_type="update_todoist_task", error=str(e))
    
    @staticmethod
    def delete_task(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Deleta tarefa do Todoist."""
        try:
            from app.services.todoist_service import get_todoist_service
            
            service = get_todoist_service()
            titulo_ou_id = params.get("titulo_ou_id", "")
            
            tasks = TodoistExecutor._run_async(service.get_tasks())
            
            matching_task = None
            for task in tasks:
                if titulo_ou_id.lower() in task["content"].lower() or task["id"] == titulo_ou_id:
                    matching_task = task
                    break
            
            if matching_task:
                success = TodoistExecutor._run_async(service.delete_task(matching_task["id"]))
                if success:
                    return ExecutionResult(success=True, action_type="delete_todoist_task",
                        response_template=f"🗑️ Tarefa *{matching_task['content']}* deletada!")
            
            return ExecutionResult(success=False, action_type="delete_todoist_task", error="Tarefa não encontrada")
        except Exception as e:
            return ExecutionResult(success=False, action_type="delete_todoist_task", error=str(e))
    
    @staticmethod
    def check_alerts(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Verifica alertas de tarefas próximas do prazo."""
        try:
            from app.services.todoist_service import get_todoist_service
            
            service = get_todoist_service()
            alerts = TodoistExecutor._run_async(service.check_deadlines(user_name=user_name))
            
            if not alerts:
                template = "✅ Nenhuma tarefa urgente!"
            else:
                lines = [f"⚠️ *{len(alerts)} tarefa(s) próxima(s) do prazo:*\n"]
                for a in alerts[:5]:
                    lines.append(f"• {a.get('content', '')} - {a.get('due', '')}")
                template = "\n".join(lines)
            
            return ExecutionResult(success=True, action_type="check_todoist_alerts", data={"alerts": alerts}, response_template=template)
        except Exception as e:
            return ExecutionResult(success=False, action_type="check_todoist_alerts", error=str(e))

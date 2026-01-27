"""
Serviço para gerenciamento de Tarefas.

Funcionalidades:
- CRUD de tarefas, projetos e etiquetas
- Gestão de subtarefas
- Filtros por status, prioridade, projeto
- Alertas de tarefas próximas do vencimento
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Task, TaskStatus, TaskPriority, Project, TaskLabel
from app.models.base import RecurrenceType

logger = logging.getLogger(__name__)


class TaskService:
    """Serviço para gerenciamento de tarefas."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== TASKS ====================

    def create_task(
        self,
        user_id: int,
        title: str,
        description: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        status: TaskStatus = TaskStatus.TODO,
        due_date: Optional[datetime] = None,
        project_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        labels: Optional[List[int]] = None,
        remind_before_minutes: int = 60,
        recurrence_type: RecurrenceType = RecurrenceType.ONCE,
        estimated_minutes: Optional[int] = None,
    ) -> Task:
        """Cria uma nova tarefa."""
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            due_date=due_date,
            project_id=project_id,
            parent_id=parent_id,
            labels=labels or [],
            remind_before_minutes=remind_before_minutes,
            recurrence_type=recurrence_type,
            estimated_minutes=estimated_minutes,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        logger.info(f"Tarefa criada: ID {task.id} - {title}")
        return task

    def create_from_entities(self, user_id: int, data: Dict[str, Any]) -> Task:
        """Cria tarefa a partir de entidades extraídas pela IA."""
        from dateutil import parser

        title = data.get("title", data.get("titulo", "Nova tarefa"))
        description = data.get("description", data.get("descricao"))
        
        # Prioridade
        priority_str = data.get("priority", data.get("prioridade", "medium")).lower()
        priority_map = {"low": TaskPriority.LOW, "medium": TaskPriority.MEDIUM, 
                        "high": TaskPriority.HIGH, "urgent": TaskPriority.URGENT,
                        "baixa": TaskPriority.LOW, "media": TaskPriority.MEDIUM,
                        "alta": TaskPriority.HIGH, "urgente": TaskPriority.URGENT}
        priority = priority_map.get(priority_str, TaskPriority.MEDIUM)
        
        # Status
        status_str = data.get("status", "todo").lower()
        status_map = {"backlog": TaskStatus.BACKLOG, "todo": TaskStatus.TODO,
                      "in_progress": TaskStatus.IN_PROGRESS, "done": TaskStatus.DONE}
        status = status_map.get(status_str, TaskStatus.TODO)
        
        # Data de vencimento
        due_date = None
        due_str = data.get("due_date", data.get("data_vencimento", data.get("date")))
        if due_str:
            try:
                if isinstance(due_str, str):
                    due_date = parser.parse(due_str)
                elif isinstance(due_str, datetime):
                    due_date = due_str
            except Exception:
                pass
        
        # Projeto
        project_id = data.get("project_id", data.get("projeto_id"))
        
        return self.create_task(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            due_date=due_date,
            project_id=project_id,
        )

    def get_task(self, user_id: int, task_id: int) -> Optional[Task]:
        """Busca tarefa por ID."""
        return self.db.query(Task).filter(
            and_(Task.id == task_id, Task.user_id == user_id)
        ).first()

    def list_tasks(
        self,
        user_id: int,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        project_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        include_subtasks: bool = False,
        only_root: bool = True,
        limit: int = 50,
    ) -> List[Task]:
        """Lista tarefas com filtros."""
        query = self.db.query(Task).filter(
            and_(Task.user_id == user_id, Task.is_active == True)
        )
        
        if status:
            query = query.filter(Task.status == status)
        else:
            query = query.filter(Task.status != TaskStatus.CANCELLED)
        
        if priority:
            query = query.filter(Task.priority == priority)
        
        if project_id:
            query = query.filter(Task.project_id == project_id)
        
        if only_root and not include_subtasks:
            query = query.filter(Task.parent_id == None)
        elif parent_id:
            query = query.filter(Task.parent_id == parent_id)
        
        return query.order_by(Task.due_date.asc().nullslast(), Task.priority.desc()).limit(limit).all()

    def update_task(self, user_id: int, task_id: int, data: Dict[str, Any]) -> Optional[Task]:
        """Atualiza tarefa."""
        task = self.get_task(user_id, task_id)
        if not task:
            return None
        
        for key, value in data.items():
            if hasattr(task, key) and value is not None:
                if key == "status" and isinstance(value, str):
                    value = TaskStatus(value)
                elif key == "priority" and isinstance(value, str):
                    value = TaskPriority(value)
                setattr(task, key, value)
        
        if data.get("status") == TaskStatus.DONE or data.get("status") == "done":
            task.completed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(task)
        return task

    def complete_task(self, user_id: int, task_id: int) -> Optional[Task]:
        """Marca tarefa como concluída."""
        return self.update_task(user_id, task_id, {
            "status": TaskStatus.DONE,
            "completed_at": datetime.utcnow()
        })

    def delete_task(self, user_id: int, task_id: int) -> bool:
        """Remove tarefa (soft delete)."""
        task = self.get_task(user_id, task_id)
        if not task:
            return False
        task.is_active = False
        task.status = TaskStatus.CANCELLED
        self.db.commit()
        return True

    def get_overdue_tasks(self, user_id: int) -> List[Task]:
        """Retorna tarefas atrasadas."""
        now = datetime.utcnow()
        return self.db.query(Task).filter(
            and_(
                Task.user_id == user_id,
                Task.is_active == True,
                Task.due_date < now,
                Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED])
            )
        ).order_by(Task.due_date.asc()).all()

    def get_upcoming_tasks(self, user_id: int, hours: int = 24) -> List[Task]:
        """Retorna tarefas próximas do vencimento."""
        now = datetime.utcnow()
        future = now + timedelta(hours=hours)
        return self.db.query(Task).filter(
            and_(
                Task.user_id == user_id,
                Task.is_active == True,
                Task.due_date >= now,
                Task.due_date <= future,
                Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED])
            )
        ).order_by(Task.due_date.asc()).all()

    def get_tasks_needing_notification(self) -> List[Task]:
        """Retorna tarefas que precisam de notificação."""
        now = datetime.utcnow()
        tasks = self.db.query(Task).filter(
            and_(
                Task.is_active == True,
                Task.notified == False,
                Task.due_date != None,
                Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED])
            )
        ).all()
        
        return [
            t for t in tasks 
            if t.due_date and (t.due_date - timedelta(minutes=t.remind_before_minutes)) <= now
        ]

    def mark_as_notified(self, task_id: int) -> bool:
        """Marca tarefa como notificada."""
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.notified = True
            self.db.commit()
            return True
        return False

    def get_kanban_board(self, user_id: int, project_id: Optional[int] = None) -> Dict[str, List[Task]]:
        """Retorna tarefas organizadas em formato Kanban."""
        filters = [Task.user_id == user_id, Task.is_active == True, Task.parent_id == None]
        if project_id:
            filters.append(Task.project_id == project_id)
        
        tasks = self.db.query(Task).filter(and_(*filters)).all()
        
        return {
            "backlog": [t for t in tasks if t.status == TaskStatus.BACKLOG],
            "todo": [t for t in tasks if t.status == TaskStatus.TODO],
            "in_progress": [t for t in tasks if t.status == TaskStatus.IN_PROGRESS],
            "done": [t for t in tasks if t.status == TaskStatus.DONE],
        }

    # ==================== PROJECTS ====================

    def create_project(
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        color: str = "#3B82F6",
        icon: Optional[str] = None,
    ) -> Project:
        """Cria um novo projeto."""
        project = Project(
            user_id=user_id,
            name=name,
            description=description,
            color=color,
            icon=icon,
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list_projects(self, user_id: int) -> List[Project]:
        """Lista projetos do usuário."""
        return self.db.query(Project).filter(
            and_(Project.user_id == user_id, Project.is_active == True)
        ).order_by(Project.is_favorite.desc(), Project.name.asc()).all()

    def get_project(self, user_id: int, project_id: int) -> Optional[Project]:
        """Busca projeto por ID."""
        return self.db.query(Project).filter(
            and_(Project.id == project_id, Project.user_id == user_id)
        ).first()

    def delete_project(self, user_id: int, project_id: int) -> bool:
        """Remove projeto (soft delete)."""
        project = self.get_project(user_id, project_id)
        if not project:
            return False
        project.is_active = False
        self.db.commit()
        return True

    # ==================== LABELS ====================

    def create_label(self, user_id: int, name: str, color: str = "#6B7280") -> TaskLabel:
        """Cria uma nova etiqueta."""
        label = TaskLabel(user_id=user_id, name=name, color=color)
        self.db.add(label)
        self.db.commit()
        self.db.refresh(label)
        return label

    def list_labels(self, user_id: int) -> List[TaskLabel]:
        """Lista etiquetas do usuário."""
        return self.db.query(TaskLabel).filter(TaskLabel.user_id == user_id).all()

    def delete_label(self, user_id: int, label_id: int) -> bool:
        """Remove etiqueta."""
        label = self.db.query(TaskLabel).filter(
            and_(TaskLabel.id == label_id, TaskLabel.user_id == user_id)
        ).first()
        if label:
            self.db.delete(label)
            self.db.commit()
            return True
        return False

    # ==================== SUMMARY ====================

    def get_summary(self, user_id: int) -> Dict[str, Any]:
        """Retorna resumo das tarefas."""
        tasks = self.db.query(Task).filter(
            and_(Task.user_id == user_id, Task.is_active == True)
        ).all()
        
        now = datetime.utcnow()
        
        return {
            "total": len(tasks),
            "by_status": {
                "backlog": sum(1 for t in tasks if t.status == TaskStatus.BACKLOG),
                "todo": sum(1 for t in tasks if t.status == TaskStatus.TODO),
                "in_progress": sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS),
                "done": sum(1 for t in tasks if t.status == TaskStatus.DONE),
            },
            "by_priority": {
                "urgent": sum(1 for t in tasks if t.priority == TaskPriority.URGENT),
                "high": sum(1 for t in tasks if t.priority == TaskPriority.HIGH),
                "medium": sum(1 for t in tasks if t.priority == TaskPriority.MEDIUM),
                "low": sum(1 for t in tasks if t.priority == TaskPriority.LOW),
            },
            "overdue": sum(1 for t in tasks if t.due_date and t.due_date < now and t.status not in [TaskStatus.DONE, TaskStatus.CANCELLED]),
            "due_today": sum(1 for t in tasks if t.due_date and t.due_date.date() == now.date() and t.status not in [TaskStatus.DONE, TaskStatus.CANCELLED]),
        }

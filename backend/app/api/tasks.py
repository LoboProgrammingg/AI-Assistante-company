"""
API endpoints para gerenciamento de Tarefas.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task, TaskStatus, TaskPriority, Project, TaskLabel
from app.models.base import RecurrenceType
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ==================== SCHEMAS ====================

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: str = "medium"
    status: str = "todo"
    due_date: Optional[datetime] = None
    project_id: Optional[int] = None
    parent_id: Optional[int] = None
    labels: Optional[List[int]] = []
    remind_before_minutes: int = 60
    recurrence_type: str = "once"
    estimated_minutes: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[datetime] = None
    project_id: Optional[int] = None
    labels: Optional[List[int]] = None
    remind_before_minutes: Optional[int] = None
    estimated_minutes: Optional[int] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str
    due_date: Optional[datetime]
    project_id: Optional[int]
    parent_id: Optional[int]
    labels: List[int]
    remind_before_minutes: int
    recurrence_type: str
    estimated_minutes: Optional[int]
    actual_minutes: Optional[int]
    is_active: bool
    notified: bool
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    subtask_count: int = 0
    is_overdue: bool = False

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    color: str = "#3B82F6"
    icon: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    color: str
    icon: Optional[str]
    is_active: bool
    is_favorite: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LabelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: str = "#6B7280"


class LabelResponse(BaseModel):
    id: int
    name: str
    color: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskSummary(BaseModel):
    total: int
    by_status: dict
    by_priority: dict
    overdue: int
    due_today: int


class KanbanBoard(BaseModel):
    backlog: List[TaskResponse]
    todo: List[TaskResponse]
    in_progress: List[TaskResponse]
    done: List[TaskResponse]


# ==================== HELPER ====================

def task_to_response(task: Task) -> TaskResponse:
    """Converte Task para TaskResponse."""
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        status=task.status.value,
        priority=task.priority.value,
        due_date=task.due_date,
        project_id=task.project_id,
        parent_id=task.parent_id,
        labels=task.labels or [],
        remind_before_minutes=task.remind_before_minutes,
        recurrence_type=task.recurrence_type.value if task.recurrence_type else "once",
        estimated_minutes=task.estimated_minutes,
        actual_minutes=task.actual_minutes,
        is_active=task.is_active,
        notified=task.notified,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        subtask_count=task.subtask_count,
        is_overdue=task.is_overdue,
    )


# ==================== TASKS ENDPOINTS ====================

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria uma nova tarefa."""
    service = TaskService(db)
    
    priority = TaskPriority(data.priority) if data.priority else TaskPriority.MEDIUM
    task_status = TaskStatus(data.status) if data.status else TaskStatus.TODO
    recurrence = RecurrenceType(data.recurrence_type) if data.recurrence_type else RecurrenceType.ONCE
    
    task = service.create_task(
        user_id=current_user.id,
        title=data.title,
        description=data.description,
        priority=priority,
        status=task_status,
        due_date=data.due_date,
        project_id=data.project_id,
        parent_id=data.parent_id,
        labels=data.labels,
        remind_before_minutes=data.remind_before_minutes,
        recurrence_type=recurrence,
        estimated_minutes=data.estimated_minutes,
    )
    return task_to_response(task)


@router.get("/", response_model=List[TaskResponse])
def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    project_id: Optional[int] = None,
    include_subtasks: bool = False,
    limit: int = Query(50, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista tarefas com filtros."""
    service = TaskService(db)
    
    task_status = TaskStatus(status) if status else None
    task_priority = TaskPriority(priority) if priority else None
    
    tasks = service.list_tasks(
        user_id=current_user.id,
        status=task_status,
        priority=task_priority,
        project_id=project_id,
        include_subtasks=include_subtasks,
        limit=limit,
    )
    return [task_to_response(t) for t in tasks]


@router.get("/kanban", response_model=KanbanBoard)
def get_kanban_board(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna tarefas em formato Kanban."""
    service = TaskService(db)
    board = service.get_kanban_board(current_user.id, project_id)
    return KanbanBoard(
        backlog=[task_to_response(t) for t in board["backlog"]],
        todo=[task_to_response(t) for t in board["todo"]],
        in_progress=[task_to_response(t) for t in board["in_progress"]],
        done=[task_to_response(t) for t in board["done"]],
    )


@router.get("/summary", response_model=TaskSummary)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna resumo das tarefas."""
    service = TaskService(db)
    return service.get_summary(current_user.id)


@router.get("/overdue", response_model=List[TaskResponse])
def get_overdue_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna tarefas atrasadas."""
    service = TaskService(db)
    tasks = service.get_overdue_tasks(current_user.id)
    return [task_to_response(t) for t in tasks]


@router.get("/upcoming", response_model=List[TaskResponse])
def get_upcoming_tasks(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna tarefas próximas do vencimento."""
    service = TaskService(db)
    tasks = service.get_upcoming_tasks(current_user.id, hours)
    return [task_to_response(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Busca tarefa por ID."""
    service = TaskService(db)
    task = service.get_task(current_user.id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return task_to_response(task)


@router.get("/{task_id}/subtasks", response_model=List[TaskResponse])
def get_subtasks(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna subtarefas de uma tarefa."""
    service = TaskService(db)
    task = service.get_task(current_user.id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    subtasks = service.list_tasks(
        user_id=current_user.id,
        parent_id=task_id,
        only_root=False,
    )
    return [task_to_response(t) for t in subtasks]


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualiza tarefa."""
    service = TaskService(db)
    update_data = data.model_dump(exclude_unset=True)
    task = service.update_task(current_user.id, task_id, update_data)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return task_to_response(task)


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marca tarefa como concluída."""
    service = TaskService(db)
    task = service.complete_task(current_user.id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return task_to_response(task)


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove tarefa."""
    service = TaskService(db)
    if not service.delete_task(current_user.id, task_id):
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return {"success": True, "message": "Tarefa removida"}


# ==================== PROJECTS ENDPOINTS ====================

@router.post("/projects/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria um novo projeto."""
    service = TaskService(db)
    project = service.create_project(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        color=data.color,
        icon=data.icon,
    )
    return project


@router.get("/projects/", response_model=List[ProjectResponse])
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista projetos."""
    service = TaskService(db)
    return service.list_projects(current_user.id)


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove projeto."""
    service = TaskService(db)
    if not service.delete_project(current_user.id, project_id):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"success": True, "message": "Projeto removido"}


# ==================== LABELS ENDPOINTS ====================

@router.post("/labels/", response_model=LabelResponse, status_code=status.HTTP_201_CREATED)
def create_label(
    data: LabelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria uma nova etiqueta."""
    service = TaskService(db)
    label = service.create_label(
        user_id=current_user.id,
        name=data.name,
        color=data.color,
    )
    return label


@router.get("/labels/", response_model=List[LabelResponse])
def list_labels(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista etiquetas."""
    service = TaskService(db)
    return service.list_labels(current_user.id)


@router.delete("/labels/{label_id}")
def delete_label(
    label_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove etiqueta."""
    service = TaskService(db)
    if not service.delete_label(current_user.id, label_id):
        raise HTTPException(status_code=404, detail="Etiqueta não encontrada")
    return {"success": True, "message": "Etiqueta removida"}

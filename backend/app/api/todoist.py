"""
API endpoints para integração com Todoist.

Endpoints para gerenciar tarefas, projetos e alertas do Todoist.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.todoist_service import get_todoist_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/todoist", tags=["todoist"])


# ==================== Schemas ====================

class TaskCreate(BaseModel):
    """Schema para criar tarefa."""
    content: str = Field(..., min_length=2, max_length=500, description="Título da tarefa")
    description: Optional[str] = Field(None, description="Descrição da tarefa")
    due_string: Optional[str] = Field(None, description="Prazo em linguagem natural")
    due_datetime: Optional[str] = Field(None, description="Prazo em formato ISO")
    priority: Optional[int] = Field(1, ge=1, le=4, description="Prioridade (1-4)")
    project_id: Optional[str] = Field(None, description="ID do projeto")
    labels: Optional[list[str]] = Field(None, description="Labels")


class TaskUpdate(BaseModel):
    """Schema para atualizar tarefa."""
    content: Optional[str] = Field(None, min_length=2, max_length=500)
    description: Optional[str] = None
    due_string: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=4)


class TaskResponse(BaseModel):
    """Schema de resposta de tarefa."""
    id: str
    content: str
    description: Optional[str] = None
    due: Optional[dict] = None
    priority: int
    project_id: Optional[str] = None
    labels: Optional[list[str]] = None
    is_completed: bool = False
    url: Optional[str] = None


class AlertResponse(BaseModel):
    """Schema de resposta de alerta."""
    task_id: str
    task_title: str
    due_datetime: str
    minutes_remaining: int
    message: str
    priority: int


class StatusResponse(BaseModel):
    """Schema de status da integração."""
    configured: bool
    connected: bool
    message: str


class ProjectResponse(BaseModel):
    """Schema de resposta de projeto."""
    id: str
    name: str
    color: Optional[str] = None
    is_favorite: bool = False
    url: Optional[str] = None


# ==================== Endpoints ====================

@router.get("/status", response_model=StatusResponse)
async def get_todoist_status(
    current_user: User = Depends(get_current_user),
):
    """
    Verifica o status da integração com o Todoist.
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        return StatusResponse(
            configured=False,
            connected=False,
            message="Todoist não configurado. TODOIST_API_KEY não definida.",
        )
    
    # Testar conexão
    try:
        projects = await service.get_projects()
        return StatusResponse(
            configured=True,
            connected=True,
            message=f"Conectado! {len(projects)} projeto(s) encontrado(s).",
        )
    except Exception as e:
        logger.error(f"Erro ao conectar com Todoist: {e}")
        return StatusResponse(
            configured=True,
            connected=False,
            message=f"Erro ao conectar: {str(e)}",
        )


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    filter: Optional[str] = Query(None, description="Filtro: today, tomorrow, overdue, p1-p4"),
    project_id: Optional[str] = Query(None, description="ID do projeto"),
    include_welcome: Optional[bool] = Query(False, description="Incluir tarefas de boas-vindas"),
    current_user: User = Depends(get_current_user),
):
    """
    Lista tarefas do Todoist.
    
    Filtros disponíveis:
    - today: Tarefas de hoje
    - tomorrow: Tarefas de amanhã
    - overdue: Tarefas atrasadas
    - p1, p2, p3, p4: Por prioridade
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        raise HTTPException(status_code=503, detail="Todoist não configurado")
    
    tasks = await service.get_tasks(filter_str=filter, project_id=project_id, include_welcome=include_welcome)
    
    return tasks


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Busca uma tarefa específica pelo ID.
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        raise HTTPException(status_code=503, detail="Todoist não configurado")
    
    task = await service.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    return task


@router.post("/tasks", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    current_user: User = Depends(get_current_user),
):
    """
    Cria uma nova tarefa no Todoist.
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        raise HTTPException(status_code=503, detail="Todoist não configurado")
    
    created_task = await service.create_task(
        content=task.content,
        description=task.description,
        due_string=task.due_string,
        due_datetime=task.due_datetime,
        priority=task.priority,
        project_id=task.project_id,
        labels=task.labels,
    )
    
    if not created_task:
        raise HTTPException(status_code=500, detail="Erro ao criar tarefa")
    
    return created_task


@router.put("/tasks/{task_id}", response_model=dict)
async def update_task(
    task_id: str,
    task: TaskUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    Atualiza uma tarefa existente.
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        raise HTTPException(status_code=503, detail="Todoist não configurado")
    
    success = await service.update_task(
        task_id=task_id,
        content=task.content,
        description=task.description,
        due_string=task.due_string,
        priority=task.priority,
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Erro ao atualizar tarefa")
    
    return {"success": True, "message": "Tarefa atualizada"}


@router.post("/tasks/{task_id}/complete", response_model=dict)
async def complete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Marca uma tarefa como concluída.
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        raise HTTPException(status_code=503, detail="Todoist não configurado")
    
    success = await service.complete_task(task_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Erro ao concluir tarefa")
    
    return {"success": True, "message": "Tarefa concluída"}


@router.delete("/tasks/{task_id}", response_model=dict)
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Deleta uma tarefa.
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        raise HTTPException(status_code=503, detail="Todoist não configurado")
    
    success = await service.delete_task(task_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Erro ao deletar tarefa")
    
    return {"success": True, "message": "Tarefa deletada"}


@router.get("/alerts", response_model=list[AlertResponse])
async def get_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verifica tarefas próximas do prazo (zona de alerta).
    
    Retorna tarefas que vencem dentro do período configurado (padrão: 60 minutos).
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        raise HTTPException(status_code=503, detail="Todoist não configurado")
    
    # Buscar nome do usuário para mensagens personalizadas
    user_name = current_user.name if current_user.name else None
    
    alerts = await service.check_deadlines(user_name=user_name)
    return alerts


@router.get("/projects", response_model=list[ProjectResponse])
async def get_projects(
    include_welcome: Optional[bool] = Query(False, description="Incluir projetos de boas-vindas"),
    current_user: User = Depends(get_current_user),
):
    """
    Lista todos os projetos do Todoist.
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        raise HTTPException(status_code=503, detail="Todoist não configurado")
    
    projects = await service.get_projects(include_welcome=include_welcome)
    return projects


@router.get("/labels", response_model=list[dict])
async def list_labels(
    current_user: User = Depends(get_current_user),
):
    """
    Lista todas as labels do Todoist.
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        raise HTTPException(status_code=503, detail="Todoist não configurado")
    
    labels = await service.get_labels()
    return labels


@router.get("/tasks/today/summary", response_model=dict)
async def get_today_summary(
    current_user: User = Depends(get_current_user),
):
    """
    Retorna um resumo das tarefas de hoje.
    """
    service = get_todoist_service()
    
    if not service.is_configured:
        raise HTTPException(status_code=503, detail="Todoist não configurado")
    
    # Tarefas de hoje
    today_tasks = await service.get_tasks(filter_str="today")
    
    # Tarefas atrasadas
    overdue_tasks = await service.get_tasks(filter_str="overdue")
    
    # Alertas (próximas do prazo)
    user_name = current_user.name if current_user.name else None
    alerts = await service.check_deadlines(user_name=user_name)
    
    # Contagem por prioridade
    priority_count = {1: 0, 2: 0, 3: 0, 4: 0}
    for task in today_tasks:
        priority_count[task.get("priority", 1)] += 1
    
    return {
        "today_count": len(today_tasks),
        "overdue_count": len(overdue_tasks),
        "alerts_count": len(alerts),
        "priority_breakdown": priority_count,
        "today_tasks": today_tasks,
        "overdue_tasks": overdue_tasks,
        "alerts": alerts,
    }

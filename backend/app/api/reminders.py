import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas import (
    ReminderCreate,
    ReminderListResponse,
    ReminderResponse,
    ReminderUpdate,
)
from app.services import ReminderService

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.post("/", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    data: ReminderCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Cria novo lembrete."""
    service = ReminderService(db)
    reminder = service.create(current_user.id, data)
    return reminder


@router.get("/", response_model=ReminderListResponse)
def list_reminders(
    status: Optional[str] = Query("active", regex="^(active|completed|all)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista lembretes do usuário.

    - **status**: active, completed, all
    - **page**: Número da página
    - **limit**: Itens por página
    """
    service = ReminderService(db)
    offset = (page - 1) * limit

    reminders, total = service.list_by_user(user_id=current_user.id, status=status, limit=limit, offset=offset)

    pages = math.ceil(total / limit) if total > 0 else 1

    return ReminderListResponse(
        items=reminders, total=total, page=page, pages=pages, has_next=page < pages, has_prev=page > 1
    )


@router.get("/upcoming")
def get_upcoming_reminders(
    hours: int = Query(24, ge=1, le=168), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Retorna lembretes das próximas N horas."""
    service = ReminderService(db)
    reminders = service.get_upcoming(current_user.id, hours)
    return {"items": reminders, "count": len(reminders)}


@router.get("/{reminder_id}", response_model=ReminderResponse)
def get_reminder(reminder_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Busca lembrete por ID."""
    service = ReminderService(db)
    reminder = service.get_by_id(reminder_id, current_user.id)

    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lembrete não encontrado")

    return reminder


@router.put("/{reminder_id}", response_model=ReminderResponse)
def update_reminder(
    reminder_id: int,
    data: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualiza lembrete."""
    service = ReminderService(db)
    reminder = service.update(reminder_id, current_user.id, data)

    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lembrete não encontrado")

    return reminder


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(reminder_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove lembrete."""
    service = ReminderService(db)
    deleted = service.delete(reminder_id, current_user.id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lembrete não encontrado")

    return None


@router.post("/{reminder_id}/complete", response_model=ReminderResponse)
def complete_reminder(reminder_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Marca lembrete como concluído."""
    service = ReminderService(db)
    reminder = service.complete(reminder_id, current_user.id)

    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lembrete não encontrado")

    return reminder

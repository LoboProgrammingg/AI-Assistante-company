import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas import (
    MeetingCreate,
    MeetingListItem,
    MeetingListResponse,
    MeetingResponse,
    MeetingUpdate,
)
from app.services import MeetingService

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(data: MeetingCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cria nova reunião manualmente."""
    service = MeetingService(db)
    meeting = service.create(current_user.id, data)
    return meeting


@router.get("/", response_model=MeetingListResponse)
def list_meetings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista reuniões do usuário."""
    service = MeetingService(db)
    offset = (page - 1) * limit

    meetings, total = service.list_by_user(user_id=current_user.id, limit=limit, offset=offset)

    pages = math.ceil(total / limit) if total > 0 else 1

    items = [
        MeetingListItem(
            id=m.id,
            title=m.title,
            date=m.date,
            duration_minutes=m.duration_minutes,
            summary=m.summary[:200] + "..." if m.summary and len(m.summary) > 200 else m.summary,
            key_topics_count=len(m.key_topics) if m.key_topics else 0,
            action_items_count=len(m.action_items) if m.action_items else 0,
            participants_count=len(m.participants) if m.participants else 0,
            sentiment=m.sentiment,
            created_at=m.created_at,
        )
        for m in meetings
    ]

    return MeetingListResponse(
        items=items, total=total, page=page, pages=pages, has_next=page < pages, has_prev=page > 1
    )


@router.get("/search")
def search_meetings(
    q: str = Query(..., min_length=2, description="Termo de busca"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Busca em reuniões por palavra-chave."""
    service = MeetingService(db)
    results = service.search(current_user.id, q)
    return {"results": results, "count": len(results)}


@router.get("/action-items/pending")
def get_pending_action_items(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retorna todos os action items pendentes de todas as reuniões."""
    service = MeetingService(db)
    items = service.get_action_items_pending(current_user.id)
    return {"items": items, "count": len(items)}


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(meeting_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Busca reunião por ID com todos os detalhes."""
    service = MeetingService(db)
    meeting = service.get_by_id(meeting_id, current_user.id)

    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reunião não encontrada")

    return meeting


@router.put("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: int, data: MeetingUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Atualiza reunião."""
    service = MeetingService(db)
    meeting = service.update(meeting_id, current_user.id, data)

    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reunião não encontrada")

    return meeting


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(meeting_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove reunião."""
    service = MeetingService(db)
    deleted = service.delete(meeting_id, current_user.id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reunião não encontrada")

    return None


@router.patch("/{meeting_id}/action-items/{item_index}")
def update_action_item(
    meeting_id: int,
    item_index: int,
    status: str = Query(..., regex="^(pending|in_progress|completed)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualiza status de um action item específico."""
    service = MeetingService(db)
    meeting = service.update_action_item_status(
        meeting_id=meeting_id, user_id=current_user.id, item_index=item_index, status=status
    )

    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reunião ou item não encontrado")

    return {"message": "Status atualizado", "action_items": meeting.action_items}

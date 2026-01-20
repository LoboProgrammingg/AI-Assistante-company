from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.contact import (
    ContactBulkCreate,
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactsByGroupResponse,
    ContactUpdate,
)
from app.services.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"])


def get_contact_service(db: Session = Depends(get_db)) -> ContactService:
    return ContactService(db)


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    data: ContactCreate,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    """Cria um novo contato."""
    return service.create(current_user.id, data)


@router.post("/bulk", response_model=List[ContactResponse], status_code=status.HTTP_201_CREATED)
def create_contacts_bulk(
    data: ContactBulkCreate,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    """Cria múltiplos contatos de uma vez."""
    return service.create_bulk(current_user.id, data.contacts)


@router.get("/", response_model=ContactListResponse)
def list_contacts(
    group_name: Optional[str] = Query(None, alias="group", description="Filtrar por grupo"),
    search: Optional[str] = Query(None, description="Buscar por nome ou telefone"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    """Lista contatos com filtros e paginação."""
    result = service.list(current_user.id, group_name=group_name, search=search, page=page, limit=limit)
    return ContactListResponse(
        items=[ContactResponse.model_validate(c) for c in result["items"]],
        **{k: v for k, v in result.items() if k != "items"}
    )


@router.get("/groups", response_model=List[dict])
def get_groups_summary(
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    """Retorna contagem de contatos por grupo."""
    return service.get_groups_summary(current_user.id)


@router.get("/group/{group_name}", response_model=ContactsByGroupResponse)
def get_contacts_by_group(
    group_name: str,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    """Retorna todos os contatos de um grupo específico."""
    contacts = service.get_by_group(current_user.id, group_name)
    return ContactsByGroupResponse(
        group_name=group_name,
        count=len(contacts),
        contacts=[ContactResponse.model_validate(c) for c in contacts],
    )


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    """Busca contato por ID."""
    contact = service.get_by_id(current_user.id, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado")
    return contact


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    data: ContactUpdate,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    """Atualiza um contato existente."""
    contact = service.update(current_user.id, contact_id, data)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado")
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    """Remove um contato (soft delete)."""
    if not service.delete(current_user.id, contact_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado")
    return None


class BroadcastRequest(BaseModel):
    message: str
    group_name: Optional[str] = None
    group_names: Optional[List[str]] = None


class BroadcastResponse(BaseModel):
    sent: int
    failed: int
    recipients: List[dict]


@router.post("/broadcast", response_model=BroadcastResponse)
def send_broadcast_message(
    data: BroadcastRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Envia mensagem para grupo(s) de contatos."""
    from app.services.message_broadcast_service import MessageBroadcastService

    if not data.group_name and not data.group_names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe group_name ou group_names")

    broadcast_service = MessageBroadcastService(db)
    result = broadcast_service.send_broadcast(
        user_id=current_user.id,
        message=data.message,
        group_name=data.group_name,
        group_names=data.group_names,
        whatsapp_service=None,  # TODO: Injetar WhatsApp service quando configurado
    )

    return BroadcastResponse(**result)

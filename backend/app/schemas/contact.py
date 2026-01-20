import re
import unicodedata
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


def normalize_group_name(name: str) -> str:
    """Normaliza nome do grupo para slug (minúsculo, sem acentos, underscores)."""
    # Remove acentos
    normalized = unicodedata.normalize("NFKD", name)
    normalized = normalized.encode("ASCII", "ignore").decode("ASCII")
    # Minúsculo e substitui espaços por underscore
    normalized = normalized.lower().strip()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_]", "", normalized)
    return normalized or "outros"


# ==================== CONTACT GROUP SCHEMAS ====================


class ContactGroupBase(BaseModel):
    """Schema base para grupo de contatos."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=10)


class ContactGroupCreate(ContactGroupBase):
    """Schema para criação de grupo."""

    pass


class ContactGroupUpdate(BaseModel):
    """Schema para atualização de grupo."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=10)
    is_active: Optional[bool] = None


class ContactGroupResponse(BaseModel):
    """Schema de resposta para grupo."""

    id: int
    user_id: int
    name: str
    slug: str
    description: Optional[str]
    icon: Optional[str]
    is_active: bool
    contact_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== CONTACT SCHEMAS ====================


class ContactBase(BaseModel):
    """Schema base para Contact."""

    name: str = Field(..., min_length=1, max_length=100)
    phone_number: str = Field(..., min_length=8, max_length=20)
    group_name: str = Field(default="outros")
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[^\d+]", "", v)
        if len(cleaned) < 8:
            raise ValueError("Número de telefone inválido")
        return cleaned

    @field_validator("group_name")
    @classmethod
    def normalize_group(cls, v: str) -> str:
        return normalize_group_name(v) if v else "outros"


class ContactCreate(ContactBase):
    """Schema para criação de contato."""

    pass


class ContactUpdate(BaseModel):
    """Schema para atualização de contato."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, min_length=8, max_length=20)
    group_name: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = re.sub(r"[^\d+]", "", v)
        if len(cleaned) < 8:
            raise ValueError("Número de telefone inválido")
        return cleaned

    @field_validator("group_name")
    @classmethod
    def normalize_group(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return normalize_group_name(v)


class ContactResponse(BaseModel):
    """Schema de resposta para Contact."""

    id: int
    user_id: int
    name: str
    phone_number: str
    group_name: str
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    """Schema para listagem paginada de contatos."""

    items: List[ContactResponse]
    total: int
    page: int
    limit: int
    pages: int
    has_next: bool
    has_prev: bool


class ContactBulkCreate(BaseModel):
    """Schema para criação em lote de contatos."""

    contacts: List[ContactCreate] = Field(..., min_length=1, max_length=100)


class ContactsByGroupResponse(BaseModel):
    """Schema para contatos agrupados."""

    group_name: str
    count: int
    contacts: List[ContactResponse]


# ==================== BROADCAST SCHEMAS ====================


class BroadcastMessageRequest(BaseModel):
    """Schema para envio de mensagem em massa."""

    message: str = Field(..., min_length=1, max_length=4096)
    group_names: Optional[List[str]] = None
    contact_ids: Optional[List[int]] = None

    @field_validator("group_names")
    @classmethod
    def normalize_groups(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        return [normalize_group_name(g) for g in v]


class BroadcastRecipient(BaseModel):
    """Schema para destinatário de broadcast."""

    name: str
    phone_number: str
    status: str = "pending"
    error: Optional[str] = None


class BroadcastResult(BaseModel):
    """Schema para resultado de broadcast."""

    total: int
    sent: int
    failed: int
    recipients: List[BroadcastRecipient]

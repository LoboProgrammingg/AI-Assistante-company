from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentCategoryEnum(str, Enum):
    """Categorias de documentos."""

    WORK = "work"
    PERSONAL = "personal"
    STUDY = "study"
    FINANCE = "finance"
    HEALTH = "health"
    LEGAL = "legal"
    OTHER = "other"


class DocumentBase(BaseModel):
    """Schema base para documento."""

    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category: DocumentCategoryEnum = DocumentCategoryEnum.OTHER
    tags: List[str] = []
    send_to_ai: bool = False


class DocumentCreate(DocumentBase):
    """Schema para criação de documento (sem arquivo, será adicionado via upload)."""

    pass


class DocumentUpdate(BaseModel):
    """Schema para atualização de documento."""

    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category: Optional[DocumentCategoryEnum] = None
    tags: Optional[List[str]] = None
    send_to_ai: Optional[bool] = None


class DocumentResponse(DocumentBase):
    """Schema de resposta do documento."""

    id: int
    user_id: int
    filename: str
    original_filename: str
    file_size: int
    mime_type: Optional[str] = None
    content_text: Optional[str] = None
    embedding_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema para lista paginada de documentos."""

    items: List[DocumentResponse]
    total: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool
    ai_count: int  # Quantidade de documentos enviados para IA
    ai_limit: int  # Limite de documentos para IA (25)


class DocumentStatsResponse(BaseModel):
    """Estatísticas de documentos do usuário."""

    total_documents: int
    ai_documents: int
    ai_limit: int
    by_category: dict
    total_size_bytes: int

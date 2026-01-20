from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    """Item de ação de uma reunião."""

    task: str
    responsible: Optional[str] = None
    deadline: Optional[str] = None
    priority: str = Field(default="medium")
    status: str = Field(default="pending")


class Participant(BaseModel):
    """Participante de uma reunião."""

    name: str
    role: Optional[str] = None


class Decision(BaseModel):
    """Decisão tomada em uma reunião."""

    decision: str
    context: Optional[str] = None


class KeyTopic(BaseModel):
    """Tópico principal discutido na reunião."""

    topic: str
    summary: Optional[str] = None
    discussed_by: List[str] = Field(default_factory=list)


class MeetingBase(BaseModel):
    """Schema base para reunião."""

    title: Optional[str] = Field(None, max_length=200)
    date: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=0)


class MeetingCreate(MeetingBase):
    """Schema para criação manual de reunião."""

    summary: Optional[str] = None
    key_topics: List[str] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    participants: List[str] = Field(default_factory=list)


class MeetingUpdate(BaseModel):
    """Schema para atualização de reunião."""

    title: Optional[str] = Field(None, max_length=200)
    summary: Optional[str] = None
    key_topics: Optional[List[KeyTopic]] = None
    action_items: Optional[List[ActionItem]] = None
    participants: Optional[List[Participant]] = None
    decisions: Optional[List[Decision]] = None


class MeetingResponse(MeetingBase):
    """Schema de resposta completa de reunião."""

    id: int
    user_id: int
    audio_url: Optional[str] = None
    transcription: Optional[str] = None
    summary: Optional[str] = None
    key_topics: List[KeyTopic] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    participants: List[Participant] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    sentiment: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MeetingListItem(BaseModel):
    """Schema para item na lista de reuniões."""

    id: int
    title: Optional[str] = None
    date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    summary: Optional[str] = None
    key_topics_count: int = 0
    action_items_count: int = 0
    participants_count: int = 0
    sentiment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingListResponse(BaseModel):
    """Schema para lista paginada de reuniões."""

    items: List[MeetingListItem]
    total: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool


class MeetingSearchResult(BaseModel):
    """Resultado de busca em reuniões."""

    meeting_id: int
    title: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    relevance_score: float


class MeetingFromAI(BaseModel):
    """Schema para criação de reunião via análise da IA."""

    title: Optional[str] = None
    summary: str
    duration_estimate: Optional[int] = None
    key_topics: List[dict] = Field(default_factory=list)
    action_items: List[dict] = Field(default_factory=list)
    participants: List[dict] = Field(default_factory=list)
    decisions: List[dict] = Field(default_factory=list)
    sentiment: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)

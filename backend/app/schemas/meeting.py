from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MeetingStatusEnum(str, Enum):
    """Status do meeting."""
    NOT_RECORDED = "not_recorded"
    RECORDING = "recording"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SessionStatusEnum(str, Enum):
    """Status da sessão."""
    RECORDING = "recording"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SessionSourceTypeEnum(str, Enum):
    """Tipo de origem da sessão."""
    REALTIME = "realtime"
    MANUAL_UPLOAD = "manual_upload"


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


# ============================================================================
# Schemas para Recording/Transcription Feature
# ============================================================================

class ChunkUploadResponse(BaseModel):
    """Resposta do upload de chunk."""
    chunk_id: int
    chunk_index: int
    received: bool
    message: str = "Chunk received successfully"


class SessionCreateResponse(BaseModel):
    """Resposta da criação de sessão."""
    session_id: int
    meeting_id: int
    status: SessionStatusEnum
    upload_endpoint: str
    message: str = "Session created successfully"


class SessionStopRequest(BaseModel):
    """Request para parar sessão."""
    force: bool = False


class SessionResponse(BaseModel):
    """Resposta completa de uma sessão."""
    id: int
    meeting_id: int
    source_type: SessionSourceTypeEnum
    status: SessionStatusEnum
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    chunks_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ArtifactActionItem(BaseModel):
    """Item de ação extraído do artefato."""
    task: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0, le=1)


class ArtifactDecision(BaseModel):
    """Decisão extraída do artefato."""
    decision: str
    context: Optional[str] = None
    made_by: Optional[str] = None


class ArtifactTopic(BaseModel):
    """Tópico extraído do artefato."""
    topic: str
    summary: Optional[str] = None
    duration_estimate: Optional[str] = None


class ArtifactTimestamp(BaseModel):
    """Timestamp/highlight extraído."""
    time_ms: int
    label: str
    importance: str = "normal"


class MeetingArtifactResponse(BaseModel):
    """Resposta completa do artefato de reunião."""
    id: int
    meeting_id: int
    transcript_text: Optional[str] = None
    transcript_language: str = "pt-BR"
    executive_summary: Optional[str] = None
    short_summary: Optional[str] = None
    topics: List[ArtifactTopic] = Field(default_factory=list)
    action_items: List[ArtifactActionItem] = Field(default_factory=list)
    decisions: List[ArtifactDecision] = Field(default_factory=list)
    risks_blockers: List[str] = Field(default_factory=list)
    timestamps: List[ArtifactTimestamp] = Field(default_factory=list)
    participants_detected: List[str] = Field(default_factory=list)
    transcription_model: Optional[str] = None
    summarization_model: Optional[str] = None
    processing_time_seconds: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingDetailResponse(BaseModel):
    """Resposta detalhada de meeting com sessões e artefatos."""
    id: int
    user_id: int
    google_event_id: Optional[str] = None
    meet_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    record_enabled: bool = False
    status: MeetingStatusEnum
    error_message: Optional[str] = None
    sessions: List[SessionResponse] = Field(default_factory=list)
    artifacts: List[MeetingArtifactResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MeetingCardResponse(BaseModel):
    """Resposta para card de meeting no dashboard."""
    id: int
    google_event_id: Optional[str] = None
    meet_url: Optional[str] = None
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    record_enabled: bool = False
    status: MeetingStatusEnum
    has_transcript: bool = False
    short_summary: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingListResponseV2(BaseModel):
    """Lista de meetings para dashboard."""
    items: List[MeetingCardResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class EnableRecordingRequest(BaseModel):
    """Request para habilitar gravação."""
    enabled: bool = True


class EnableRecordingResponse(BaseModel):
    """Resposta de habilitação de gravação."""
    meeting_id: int
    record_enabled: bool
    message: str


class FileUploadResponse(BaseModel):
    """Resposta de upload de arquivo."""
    session_id: int
    meeting_id: int
    file_size_bytes: int
    status: SessionStatusEnum
    message: str = "File uploaded successfully, processing started"


class ReprocessRequest(BaseModel):
    """Request para reprocessar meeting."""
    transcribe: bool = True
    summarize: bool = True


class SyncGoogleCalendarResponse(BaseModel):
    """Resposta da sincronização com Google Calendar."""
    synced_count: int
    created_count: int
    updated_count: int
    meetings: List[MeetingCardResponse] = Field(default_factory=list)
    message: str

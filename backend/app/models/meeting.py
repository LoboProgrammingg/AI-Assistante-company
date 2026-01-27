"""
Modelo de reuniões com suporte a transcrição e gravação.
"""

import enum

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, utc_now


class MeetingStatus(enum.Enum):
    """Status do meeting."""
    NOT_RECORDED = "not_recorded"
    RECORDING = "recording"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SessionStatus(enum.Enum):
    """Status da sessão de gravação."""
    RECORDING = "recording"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SessionSourceType(enum.Enum):
    """Tipo de origem da sessão."""
    REALTIME = "realtime"
    MANUAL_UPLOAD = "manual_upload"


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Google Calendar integration
    google_event_id = Column(String, nullable=True, index=True)
    meet_url = Column(String, nullable=True)

    # Meeting details
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    date = Column(DateTime, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    # Recording settings
    record_enabled = Column(Boolean, default=False)
    status = Column(Enum(MeetingStatus), default=MeetingStatus.NOT_RECORDED)
    error_message = Column(Text, nullable=True)

    # Legacy fields (mantidos para compatibilidade)
    audio_url = Column(String, nullable=True)
    transcription = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    key_topics = Column(JSON, default=[])
    action_items = Column(JSON, default=[])
    participants = Column(JSON, default=[])
    decisions = Column(JSON, default=[])
    sentiment = Column(String, nullable=True)
    keywords = Column(JSON, default=[])

    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="meetings")
    sessions = relationship("MeetingSession", back_populates="meeting", cascade="all, delete-orphan")
    artifacts = relationship("MeetingArtifact", back_populates="meeting", cascade="all, delete-orphan")


class MeetingSession(Base):
    """Sessão de gravação de uma reunião."""
    __tablename__ = "meeting_sessions"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)

    # Session info
    source_type = Column(Enum(SessionSourceType), default=SessionSourceType.REALTIME)
    status = Column(Enum(SessionStatus), default=SessionStatus.RECORDING)
    
    # Timestamps
    started_at = Column(DateTime, default=utc_now)
    ended_at = Column(DateTime, nullable=True)
    
    # Storage
    storage_path = Column(String, nullable=True)
    assembled_audio_path = Column(String, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    meeting = relationship("Meeting", back_populates="sessions")
    chunks = relationship("MeetingChunk", back_populates="session", cascade="all, delete-orphan")


class MeetingChunk(Base):
    """Chunk de áudio de uma sessão de gravação."""
    __tablename__ = "meeting_chunks"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("meeting_sessions.id"), nullable=False)

    # Chunk info
    chunk_index = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    
    # Timing
    start_ms = Column(Integer, nullable=True)
    end_ms = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    session = relationship("MeetingSession", back_populates="chunks")


class MeetingArtifact(Base):
    """Artefatos gerados de uma reunião (transcrição, resumo)."""
    __tablename__ = "meeting_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)

    # Transcript
    transcript_text = Column(Text, nullable=True)
    transcript_language = Column(String, default="pt-BR")
    transcript_confidence = Column(Integer, nullable=True)

    # Summary (structured JSON)
    summary_json = Column(JSON, nullable=True)
    executive_summary = Column(Text, nullable=True)
    short_summary = Column(String(500), nullable=True)

    # Extracted data
    topics = Column(JSON, default=[])
    action_items = Column(JSON, default=[])
    decisions = Column(JSON, default=[])
    risks_blockers = Column(JSON, default=[])
    timestamps = Column(JSON, default=[])
    participants_detected = Column(JSON, default=[])

    # Model info
    transcription_model = Column(String, nullable=True)
    summarization_model = Column(String, nullable=True)
    processing_time_seconds = Column(Integer, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    meeting = relationship("Meeting", back_populates="artifacts")

"""
API de Meetings v2 - Endpoints para gravação e transcrição de reuniões.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Meeting, MeetingArtifact, MeetingSession, MeetingStatus, SessionStatus, User
from app.schemas.meeting import (
    ChunkUploadResponse,
    EnableRecordingRequest,
    EnableRecordingResponse,
    FileUploadResponse,
    MeetingCardResponse,
    MeetingDetailResponse,
    MeetingListResponseV2,
    MeetingStatusEnum,
    ReprocessRequest,
    SessionCreateResponse,
    SessionResponse,
    SessionStatusEnum,
    SyncGoogleCalendarResponse,
)
from app.services.meeting_transcription_service import MeetingTranscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["meetings-v2"])


def _meeting_to_card(meeting: Meeting) -> MeetingCardResponse:
    """Converte Meeting para MeetingCardResponse."""
    has_transcript = False
    short_summary = None

    if meeting.artifacts:
        artifact = meeting.artifacts[0]
        has_transcript = bool(artifact.transcript_text)
        short_summary = artifact.short_summary

    return MeetingCardResponse(
        id=meeting.id,
        google_event_id=meeting.google_event_id,
        meet_url=meeting.meet_url,
        title=meeting.title,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        record_enabled=meeting.record_enabled,
        status=MeetingStatusEnum(meeting.status.value) if meeting.status else MeetingStatusEnum.NOT_RECORDED,
        has_transcript=has_transcript,
        short_summary=short_summary,
        created_at=meeting.created_at,
    )


def _session_to_response(session: MeetingSession) -> SessionResponse:
    """Converte MeetingSession para SessionResponse."""
    return SessionResponse(
        id=session.id,
        meeting_id=session.meeting_id,
        source_type=session.source_type.value,
        status=SessionStatusEnum(session.status.value),
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_seconds=session.duration_seconds,
        chunks_count=len(session.chunks) if session.chunks else 0,
        error_message=session.error_message,
        created_at=session.created_at,
    )


# =============================================================================
# Meeting List & Details
# =============================================================================

@router.get("", response_model=MeetingListResponseV2)
def list_meetings(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    upcoming_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista meetings do usuário com paginação."""
    query = db.query(Meeting).filter(Meeting.user_id == current_user.id)

    # Filtros
    if status_filter:
        try:
            status_enum = MeetingStatus(status_filter)
            query = query.filter(Meeting.status == status_enum)
        except ValueError:
            pass

    if upcoming_only:
        now = datetime.now(timezone.utc)
        query = query.filter(Meeting.start_time >= now)

    # Ordenar por data
    query = query.order_by(Meeting.start_time.desc())

    # Paginação
    total = query.count()
    offset = (page - 1) * per_page
    meetings = query.offset(offset).limit(per_page).all()

    items = [_meeting_to_card(m) for m in meetings]
    pages = (total + per_page - 1) // per_page

    return MeetingListResponseV2(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        has_next=page < pages,
        has_prev=page > 1,
    )


@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
def get_meeting_detail(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna detalhes completos de um meeting."""
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id,
        Meeting.user_id == current_user.id,
    ).first()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting não encontrado")

    sessions = [_session_to_response(s) for s in meeting.sessions]
    artifacts = []

    for artifact in meeting.artifacts:
        artifacts.append({
            "id": artifact.id,
            "meeting_id": artifact.meeting_id,
            "transcript_text": artifact.transcript_text,
            "transcript_language": artifact.transcript_language,
            "executive_summary": artifact.executive_summary,
            "short_summary": artifact.short_summary,
            "topics": artifact.topics or [],
            "action_items": artifact.action_items or [],
            "decisions": artifact.decisions or [],
            "risks_blockers": artifact.risks_blockers or [],
            "timestamps": artifact.timestamps or [],
            "participants_detected": artifact.participants_detected or [],
            "transcription_model": artifact.transcription_model,
            "summarization_model": artifact.summarization_model,
            "processing_time_seconds": artifact.processing_time_seconds,
            "created_at": artifact.created_at,
        })

    return MeetingDetailResponse(
        id=meeting.id,
        user_id=meeting.user_id,
        google_event_id=meeting.google_event_id,
        meet_url=meeting.meet_url,
        title=meeting.title,
        description=meeting.description,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        duration_minutes=meeting.duration_minutes,
        record_enabled=meeting.record_enabled,
        status=MeetingStatusEnum(meeting.status.value) if meeting.status else MeetingStatusEnum.NOT_RECORDED,
        error_message=meeting.error_message,
        sessions=sessions,
        artifacts=artifacts,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
    )


# =============================================================================
# Recording Controls
# =============================================================================

@router.post("/{meeting_id}/enable-recording", response_model=EnableRecordingResponse)
def enable_recording(
    meeting_id: int,
    request: EnableRecordingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Habilita/desabilita gravação para um meeting."""
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id,
        Meeting.user_id == current_user.id,
    ).first()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting não encontrado")

    meeting.record_enabled = request.enabled
    db.commit()

    action = "habilitada" if request.enabled else "desabilitada"
    return EnableRecordingResponse(
        meeting_id=meeting_id,
        record_enabled=meeting.record_enabled,
        message=f"Gravação {action} com sucesso",
    )


@router.post("/{meeting_id}/sessions", response_model=SessionCreateResponse)
def start_recording_session(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Inicia uma nova sessão de gravação (real-time)."""
    service = MeetingTranscriptionService(db)

    try:
        session = service.create_session(
            meeting_id=meeting_id,
            user_id=current_user.id,
        )

        return SessionCreateResponse(
            session_id=session.id,
            meeting_id=meeting_id,
            status=SessionStatusEnum(session.status.value),
            upload_endpoint=f"/api/v1/meetings/{meeting_id}/sessions/{session.id}/chunks",
            message="Sessão de gravação iniciada",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{meeting_id}/sessions/{session_id}/chunks", response_model=ChunkUploadResponse)
async def upload_chunk(
    meeting_id: int,
    session_id: int,
    chunk_index: int = Query(..., ge=0),
    start_ms: Optional[int] = Query(None),
    end_ms: Optional[int] = Query(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload de chunk de áudio."""
    service = MeetingTranscriptionService(db)

    try:
        chunk_data = await file.read()
        
        chunk = service.add_chunk(
            session_id=session_id,
            user_id=current_user.id,
            chunk_data=chunk_data,
            chunk_index=chunk_index,
            start_ms=start_ms,
            end_ms=end_ms,
        )

        return ChunkUploadResponse(
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            received=True,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{meeting_id}/sessions/{session_id}/stop")
async def stop_recording_session(
    meeting_id: int,
    session_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Para a sessão de gravação e inicia processamento."""
    service = MeetingTranscriptionService(db)

    try:
        session = service.stop_session(
            session_id=session_id,
            user_id=current_user.id,
        )

        # Processar em background
        background_tasks.add_task(
            _process_session_async,
            session_id=session_id,
        )

        return {
            "session_id": session_id,
            "status": session.status.value,
            "message": "Gravação finalizada. Processamento iniciado.",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Manual Upload
# =============================================================================

@router.post("/{meeting_id}/upload", response_model=FileUploadResponse)
async def upload_recording(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload manual de arquivo de áudio/vídeo."""
    # Validar extensão
    allowed_extensions = {".mp3", ".wav", ".m4a", ".webm", ".mp4", ".ogg"}
    file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado. Use: {', '.join(allowed_extensions)}",
        )

    service = MeetingTranscriptionService(db)

    try:
        file_data = await file.read()
        
        session = service.upload_file(
            meeting_id=meeting_id,
            user_id=current_user.id,
            file_data=file_data,
            filename=file.filename,
        )

        # Processar em background
        background_tasks.add_task(
            _process_session_async,
            session_id=session.id,
        )

        return FileUploadResponse(
            session_id=session.id,
            meeting_id=meeting_id,
            file_size_bytes=len(file_data),
            status=SessionStatusEnum(session.status.value),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Reprocessing
# =============================================================================

@router.post("/{meeting_id}/reprocess")
async def reprocess_meeting(
    meeting_id: int,
    request: ReprocessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reprocessa transcrição/sumarização de um meeting."""
    meeting = db.query(Meeting).filter(
        Meeting.id == meeting_id,
        Meeting.user_id == current_user.id,
    ).first()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting não encontrado")

    # Buscar última sessão
    session = db.query(MeetingSession).filter(
        MeetingSession.meeting_id == meeting_id,
    ).order_by(MeetingSession.created_at.desc()).first()

    if not session:
        raise HTTPException(status_code=400, detail="Nenhuma sessão encontrada para reprocessar")

    # Resetar status
    session.status = SessionStatus.PROCESSING
    meeting.status = MeetingStatus.PROCESSING
    meeting.error_message = None
    db.commit()

    # Processar em background
    background_tasks.add_task(
        _process_session_async,
        session_id=session.id,
    )

    return {
        "meeting_id": meeting_id,
        "session_id": session.id,
        "message": "Reprocessamento iniciado",
    }


# =============================================================================
# Google Calendar Sync
# =============================================================================

@router.post("/sync-google-calendar", response_model=SyncGoogleCalendarResponse)
def sync_google_calendar(
    days_ahead: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sincroniza meetings do Google Calendar."""
    from app.services.google_calendar_service import GoogleCalendarService

    calendar_service = GoogleCalendarService(db)

    if not calendar_service.is_user_connected(current_user.id):
        raise HTTPException(
            status_code=400,
            detail="Google Calendar não conectado. Conecte nas Configurações.",
        )

    # Buscar eventos
    time_max = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    result = calendar_service.list_events(
        user_id=current_user.id,
        max_results=100,
        time_max=time_max,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Erro ao buscar eventos"))

    # Sincronizar
    meeting_service = MeetingTranscriptionService(db)
    sync_result = meeting_service.sync_from_google_calendar(
        user_id=current_user.id,
        events=result.get("events", []),
    )

    # Buscar meetings atualizados
    meetings = db.query(Meeting).filter(
        Meeting.user_id == current_user.id,
        Meeting.google_event_id.isnot(None),
    ).order_by(Meeting.start_time.desc()).limit(20).all()

    return SyncGoogleCalendarResponse(
        synced_count=sync_result["created"] + sync_result["updated"],
        created_count=sync_result["created"],
        updated_count=sync_result["updated"],
        meetings=[_meeting_to_card(m) for m in meetings],
        message=f"Sincronizados {sync_result['created']} novos e {sync_result['updated']} atualizados",
    )


# =============================================================================
# Background Task Helper
# =============================================================================

def _process_session_async(session_id: int):
    """Wrapper para processar sessão em background."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        service = MeetingTranscriptionService(db)
        asyncio.run(service.process_session(session_id))
    except Exception as e:
        logger.error(f"[MEETING] Background processing failed: {e}")
    finally:
        db.close()

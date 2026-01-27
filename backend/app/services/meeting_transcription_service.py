"""
Meeting Transcription Service - Serviço para transcrição e sumarização de reuniões.
"""

import asyncio
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai.graph_v3.prompts import SUMMARIZATION_PROMPT, TRANSCRIPTION_PROMPT
from app.config import settings
from app.models.meeting import (
    Meeting,
    MeetingArtifact,
    MeetingChunk,
    MeetingSession,
    MeetingStatus,
    SessionSourceType,
    SessionStatus,
)

logger = logging.getLogger(__name__)

# Diretório para armazenamento de áudio
AUDIO_STORAGE_PATH = getattr(settings, "AUDIO_STORAGE_PATH", "/tmp/iris_audio")


class MeetingTranscriptionService:
    """Serviço para transcrição e sumarização de reuniões."""

    def __init__(self, db: Session):
        self.db = db
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        """Garante que o diretório de armazenamento existe."""
        Path(AUDIO_STORAGE_PATH).mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Session Management
    # =========================================================================

    def create_session(
        self,
        meeting_id: int,
        user_id: int,
        source_type: SessionSourceType = SessionSourceType.REALTIME,
    ) -> MeetingSession:
        """Cria uma nova sessão de gravação."""
        # Verificar se meeting existe e pertence ao usuário
        meeting = self.db.query(Meeting).filter(
            Meeting.id == meeting_id,
            Meeting.user_id == user_id,
        ).first()

        if not meeting:
            raise ValueError("Meeting não encontrado ou não pertence ao usuário")

        # Criar diretório para a sessão
        session_dir = os.path.join(AUDIO_STORAGE_PATH, str(user_id), str(meeting_id))
        Path(session_dir).mkdir(parents=True, exist_ok=True)

        # Criar sessão
        session = MeetingSession(
            meeting_id=meeting_id,
            source_type=source_type,
            status=SessionStatus.RECORDING,
            storage_path=session_dir,
        )

        self.db.add(session)

        # Atualizar status do meeting
        meeting.status = MeetingStatus.RECORDING
        meeting.record_enabled = True

        self.db.commit()
        self.db.refresh(session)

        logger.info(f"[MEETING] Session {session.id} created for meeting {meeting_id}")
        return session

    def add_chunk(
        self,
        session_id: int,
        user_id: int,
        chunk_data: bytes,
        chunk_index: int,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> MeetingChunk:
        """Adiciona um chunk de áudio à sessão."""
        # Verificar sessão e permissões
        session = self.db.query(MeetingSession).join(Meeting).filter(
            MeetingSession.id == session_id,
            Meeting.user_id == user_id,
        ).first()

        if not session:
            raise ValueError("Sessão não encontrada ou não pertence ao usuário")

        if session.status not in [SessionStatus.RECORDING, SessionStatus.UPLOADING]:
            raise ValueError(f"Sessão não está em modo de gravação: {session.status}")

        # Salvar chunk em arquivo
        chunk_filename = f"chunk_{chunk_index:05d}.webm"
        chunk_path = os.path.join(session.storage_path, chunk_filename)

        with open(chunk_path, "wb") as f:
            f.write(chunk_data)

        # Criar registro do chunk
        chunk = MeetingChunk(
            session_id=session_id,
            chunk_index=chunk_index,
            file_path=chunk_path,
            file_size_bytes=len(chunk_data),
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=(end_ms - start_ms) if start_ms and end_ms else None,
        )

        self.db.add(chunk)
        session.status = SessionStatus.UPLOADING
        self.db.commit()
        self.db.refresh(chunk)

        logger.debug(f"[MEETING] Chunk {chunk_index} added to session {session_id}")
        return chunk

    def stop_session(self, session_id: int, user_id: int) -> MeetingSession:
        """Para uma sessão de gravação e inicia processamento."""
        session = self.db.query(MeetingSession).join(Meeting).filter(
            MeetingSession.id == session_id,
            Meeting.user_id == user_id,
        ).first()

        if not session:
            raise ValueError("Sessão não encontrada")

        session.ended_at = datetime.now(timezone.utc)
        session.status = SessionStatus.PROCESSING

        # Atualizar meeting
        meeting = session.meeting
        meeting.status = MeetingStatus.PROCESSING

        self.db.commit()
        self.db.refresh(session)

        logger.info(f"[MEETING] Session {session_id} stopped, starting processing")
        return session

    # =========================================================================
    # File Upload (Manual)
    # =========================================================================

    def upload_file(
        self,
        meeting_id: int,
        user_id: int,
        file_data: bytes,
        filename: str,
    ) -> MeetingSession:
        """Upload manual de arquivo de áudio/vídeo."""
        meeting = self.db.query(Meeting).filter(
            Meeting.id == meeting_id,
            Meeting.user_id == user_id,
        ).first()

        if not meeting:
            raise ValueError("Meeting não encontrado")

        # Criar diretório
        session_dir = os.path.join(AUDIO_STORAGE_PATH, str(user_id), str(meeting_id))
        Path(session_dir).mkdir(parents=True, exist_ok=True)

        # Salvar arquivo
        file_path = os.path.join(session_dir, filename)
        with open(file_path, "wb") as f:
            f.write(file_data)

        # Criar sessão
        session = MeetingSession(
            meeting_id=meeting_id,
            source_type=SessionSourceType.MANUAL_UPLOAD,
            status=SessionStatus.PROCESSING,
            storage_path=session_dir,
            assembled_audio_path=file_path,
            file_size_bytes=len(file_data),
        )

        self.db.add(session)

        meeting.status = MeetingStatus.PROCESSING
        meeting.record_enabled = True

        self.db.commit()
        self.db.refresh(session)

        logger.info(f"[MEETING] File uploaded for meeting {meeting_id}: {filename}")
        return session

    # =========================================================================
    # Audio Processing
    # =========================================================================

    def assemble_chunks(self, session_id: int) -> str:
        """Monta os chunks de áudio em um único arquivo."""
        session = self.db.query(MeetingSession).filter(
            MeetingSession.id == session_id
        ).first()

        if not session:
            raise ValueError("Sessão não encontrada")

        chunks = self.db.query(MeetingChunk).filter(
            MeetingChunk.session_id == session_id
        ).order_by(MeetingChunk.chunk_index).all()

        if not chunks:
            raise ValueError("Nenhum chunk encontrado na sessão")

        # Arquivo de saída
        output_path = os.path.join(session.storage_path, "assembled.webm")

        # Montar arquivo (concatenação simples para webm)
        with open(output_path, "wb") as outfile:
            for chunk in chunks:
                with open(chunk.file_path, "rb") as infile:
                    outfile.write(infile.read())

        session.assembled_audio_path = output_path
        session.file_size_bytes = os.path.getsize(output_path)

        self.db.commit()

        logger.info(f"[MEETING] Assembled {len(chunks)} chunks into {output_path}")
        return output_path

    # =========================================================================
    # Transcription
    # =========================================================================

    async def transcribe_audio(self, audio_path: str, language: str = "pt-BR") -> Dict[str, Any]:
        """Transcreve áudio usando speech-to-text."""
        try:
            import google.generativeai as genai

            # Configurar Gemini
            api_key = getattr(settings, "GEMINI_API_KEY", None)
            if not api_key:
                raise ValueError("GEMINI_API_KEY não configurada")

            genai.configure(api_key=api_key)

            # Upload do arquivo para Gemini
            logger.info(f"[TRANSCRIPTION] Uploading audio file: {audio_path}")

            audio_file = genai.upload_file(audio_path)

            # Aguardar processamento
            while audio_file.state.name == "PROCESSING":
                await asyncio.sleep(2)
                audio_file = genai.get_file(audio_file.name)

            if audio_file.state.name == "FAILED":
                raise ValueError("Falha no upload do arquivo de áudio")

            # Usar Gemini para transcrever
            model = genai.GenerativeModel("gemini-2.5-pro")

            prompt = TRANSCRIPTION_PROMPT.format(language=language)

            response = model.generate_content([prompt, audio_file])

            # Limpar arquivo do Gemini
            genai.delete_file(audio_file.name)

            transcript = response.text.strip()

            logger.info(f"[TRANSCRIPTION] Completed: {len(transcript)} chars")

            return {
                "success": True,
                "transcript": transcript,
                "language": language,
                "model": "gemini-2.0-flash",
            }

        except Exception as e:
            logger.error(f"[TRANSCRIPTION] Error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # =========================================================================
    # Summarization
    # =========================================================================

    async def summarize_transcript(self, transcript: str) -> Dict[str, Any]:
        """Sumariza a transcrição usando LLM."""
        try:
            import google.generativeai as genai

            api_key = getattr(settings, "GEMINI_API_KEY", None)
            if not api_key:
                raise ValueError("GEMINI_API_KEY não configurada")

            genai.configure(api_key=api_key)

            model = genai.GenerativeModel("gemini-2.5-pro")

            prompt = SUMMARIZATION_PROMPT.format(transcript=transcript)

            response = model.generate_content(prompt)
            response_text = response.text.strip()

            # Limpar markdown se presente
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            import json
            summary_data = json.loads(response_text)

            logger.info(f"[SUMMARIZATION] Completed successfully")

            return {
                "success": True,
                "summary": summary_data,
                "model": "gemini-2.0-flash",
            }

        except Exception as e:
            logger.error(f"[SUMMARIZATION] Error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # =========================================================================
    # Full Processing Pipeline
    # =========================================================================

    async def process_session(self, session_id: int) -> MeetingArtifact:
        """Processa uma sessão completa: montar, transcrever, sumarizar."""
        start_time = time.time()

        session = self.db.query(MeetingSession).filter(
            MeetingSession.id == session_id
        ).first()

        if not session:
            raise ValueError("Sessão não encontrada")

        meeting = session.meeting

        try:
            # 1. Montar chunks se necessário
            audio_path = session.assembled_audio_path
            if not audio_path and session.source_type == SessionSourceType.REALTIME:
                audio_path = self.assemble_chunks(session_id)

            if not audio_path or not os.path.exists(audio_path):
                raise ValueError("Arquivo de áudio não encontrado")

            # 2. Transcrever
            logger.info(f"[MEETING] Transcribing session {session_id}")
            transcription_result = await self.transcribe_audio(audio_path)

            if not transcription_result.get("success"):
                raise ValueError(f"Falha na transcrição: {transcription_result.get('error')}")

            transcript = transcription_result.get("transcript", "")

            # 3. Sumarizar
            logger.info(f"[MEETING] Summarizing session {session_id}")
            summary_result = await self.summarize_transcript(transcript)

            summary_data = {}
            if summary_result.get("success"):
                summary_data = summary_result.get("summary", {})

            # 4. Criar artefato
            processing_time = int(time.time() - start_time)

            artifact = MeetingArtifact(
                meeting_id=meeting.id,
                transcript_text=transcript,
                transcript_language="pt-BR",
                summary_json=summary_data,
                executive_summary=summary_data.get("executive_summary"),
                short_summary=summary_data.get("short_summary", "")[:500],
                topics=summary_data.get("topics", []),
                action_items=summary_data.get("action_items", []),
                decisions=summary_data.get("decisions", []),
                risks_blockers=summary_data.get("risks_blockers", []),
                participants_detected=summary_data.get("participants_detected", []),
                transcription_model=transcription_result.get("model"),
                summarization_model=summary_result.get("model"),
                processing_time_seconds=processing_time,
            )

            self.db.add(artifact)

            # 5. Atualizar status
            session.status = SessionStatus.READY
            meeting.status = MeetingStatus.READY
            meeting.transcription = transcript
            meeting.summary = summary_data.get("executive_summary")
            meeting.action_items = summary_data.get("action_items", [])
            meeting.decisions = summary_data.get("decisions", [])
            meeting.key_topics = summary_data.get("topics", [])

            self.db.commit()
            self.db.refresh(artifact)

            logger.info(f"[MEETING] Session {session_id} processed in {processing_time}s")
            return artifact

        except Exception as e:
            logger.error(f"[MEETING] Processing failed for session {session_id}: {e}")

            session.status = SessionStatus.FAILED
            session.error_message = str(e)
            meeting.status = MeetingStatus.FAILED
            meeting.error_message = str(e)

            self.db.commit()
            raise

    # =========================================================================
    # Google Calendar Sync
    # =========================================================================

    def sync_from_google_calendar(self, user_id: int, events: List[Dict]) -> Dict[str, int]:
        """Sincroniza meetings do Google Calendar."""
        created = 0
        updated = 0

        for event in events:
            google_event_id = event.get("id")
            meet_link = event.get("hangoutLink") or event.get("conferenceData", {}).get(
                "entryPoints", [{}]
            )[0].get("uri")

            # Só importar eventos com Google Meet
            if not meet_link:
                continue

            # Verificar se já existe
            existing = self.db.query(Meeting).filter(
                Meeting.user_id == user_id,
                Meeting.google_event_id == google_event_id,
            ).first()

            start_time = None
            end_time = None
            
            start = event.get("start", {})
            if start.get("dateTime"):
                start_time = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
            
            end = event.get("end", {})
            if end.get("dateTime"):
                end_time = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))

            if existing:
                # Atualizar
                existing.title = event.get("summary", "Sem título")
                existing.description = event.get("description")
                existing.start_time = start_time
                existing.end_time = end_time
                existing.meet_url = meet_link
                updated += 1
            else:
                # Criar novo
                meeting = Meeting(
                    user_id=user_id,
                    google_event_id=google_event_id,
                    title=event.get("summary", "Sem título"),
                    description=event.get("description"),
                    start_time=start_time,
                    end_time=end_time,
                    date=start_time,
                    meet_url=meet_link,
                    status=MeetingStatus.NOT_RECORDED,
                )
                self.db.add(meeting)
                created += 1

        self.db.commit()

        logger.info(f"[MEETING] Synced from Google Calendar: {created} created, {updated} updated")
        return {"created": created, "updated": updated}

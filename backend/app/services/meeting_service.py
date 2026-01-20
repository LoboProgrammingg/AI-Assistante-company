import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def utc_now():
    """Retorna datetime atual em UTC."""
    return datetime.now(timezone.utc)


from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import Meeting
from app.schemas.meeting import MeetingCreate, MeetingUpdate

logger = logging.getLogger(__name__)


class MeetingService:
    """Serviço para gerenciamento de reuniões."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, data: MeetingCreate) -> Meeting:
        """
        Cria uma nova reunião manualmente.

        Args:
            user_id: ID do usuário
            data: Dados da reunião

        Returns:
            Meeting: Reunião criada
        """
        meeting = Meeting(
            user_id=user_id,
            title=data.title,
            date=data.date or utc_now(),
            duration_minutes=data.duration_minutes,
            summary=data.summary,
            key_topics=[{"topic": t} for t in data.key_topics],
            action_items=[item.model_dump() for item in data.action_items],
            participants=[{"name": p} for p in data.participants],
        )

        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)

        logger.info(f"Reunião criada: {meeting.id}")
        return meeting

    def create_from_entities(
        self, user_id: int, entities: dict, audio_url: Optional[str] = None, transcription: Optional[str] = None
    ) -> Meeting:
        """
        Cria reunião a partir de análise da IA.

        Args:
            user_id: ID do usuário
            entities: Entidades extraídas pela IA
            audio_url: URL do áudio original
            transcription: Transcrição do áudio

        Returns:
            Meeting: Reunião criada
        """
        meeting = Meeting(
            user_id=user_id,
            title=entities.get("title"),
            date=utc_now(),
            duration_minutes=entities.get("duration_estimate"),
            audio_url=audio_url,
            transcription=transcription,
            summary=entities.get("summary"),
            key_topics=entities.get("key_topics", []),
            action_items=entities.get("action_items", []),
            participants=entities.get("participants", []),
            decisions=entities.get("decisions", []),
            sentiment=entities.get("sentiment"),
            keywords=entities.get("keywords", []),
        )

        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)

        logger.info(f"Reunião criada via IA: {meeting.id}")
        return meeting

    def get_by_id(self, meeting_id: int, user_id: int) -> Optional[Meeting]:
        """Busca reunião por ID."""
        return self.db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.user_id == user_id).first()

    def list_by_user(self, user_id: int, limit: int = 20, offset: int = 0) -> Tuple[List[Meeting], int]:
        """
        Lista reuniões do usuário com paginação.

        Args:
            user_id: ID do usuário
            limit: Quantidade por página
            offset: Offset para paginação

        Returns:
            Tuple: (lista de reuniões, total)
        """
        query = self.db.query(Meeting).filter(Meeting.user_id == user_id)

        total = query.count()

        meetings = query.order_by(Meeting.created_at.desc()).offset(offset).limit(limit).all()

        return meetings, total

    def update(self, meeting_id: int, user_id: int, data: MeetingUpdate) -> Optional[Meeting]:
        """Atualiza uma reunião."""
        meeting = self.get_by_id(meeting_id, user_id)
        if not meeting:
            return None

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if value is not None:
                if field in ["key_topics", "action_items", "participants", "decisions"]:
                    value = [item.model_dump() if hasattr(item, "model_dump") else item for item in value]
                setattr(meeting, field, value)

        meeting.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(meeting)

        logger.info(f"Reunião atualizada: {meeting_id}")
        return meeting

    def delete(self, meeting_id: int, user_id: int) -> bool:
        """Remove uma reunião."""
        meeting = self.get_by_id(meeting_id, user_id)
        if not meeting:
            return False

        self.db.delete(meeting)
        self.db.commit()

        logger.info(f"Reunião removida: {meeting_id}")
        return True

    def search(self, user_id: int, query: str) -> List[Dict[str, Any]]:
        """
        Busca em reuniões por palavra-chave.

        Args:
            user_id: ID do usuário
            query: Termo de busca

        Returns:
            Lista de resultados com highlights
        """
        meetings = (
            self.db.query(Meeting)
            .filter(
                Meeting.user_id == user_id,
                or_(
                    Meeting.title.ilike(f"%{query}%"),
                    Meeting.summary.ilike(f"%{query}%"),
                    Meeting.transcription.ilike(f"%{query}%"),
                ),
            )
            .all()
        )

        results = []
        for m in meetings:
            highlights = []

            if m.title and query.lower() in m.title.lower():
                highlights.append(m.title)

            if m.summary and query.lower() in m.summary.lower():
                idx = m.summary.lower().find(query.lower())
                start = max(0, idx - 50)
                end = min(len(m.summary), idx + len(query) + 50)
                highlights.append(f"...{m.summary[start:end]}...")

            results.append(
                {
                    "meeting_id": m.id,
                    "title": m.title,
                    "date": m.date.isoformat() if m.date else None,
                    "highlights": highlights,
                    "relevance_score": 0.9 if m.title and query.lower() in m.title.lower() else 0.7,
                }
            )

        return sorted(results, key=lambda x: x["relevance_score"], reverse=True)

    def update_action_item_status(
        self, meeting_id: int, user_id: int, item_index: int, status: str
    ) -> Optional[Meeting]:
        """
        Atualiza status de um action item.

        Args:
            meeting_id: ID da reunião
            user_id: ID do usuário
            item_index: Índice do item
            status: Novo status

        Returns:
            Meeting atualizado ou None
        """
        meeting = self.get_by_id(meeting_id, user_id)
        if not meeting:
            return None

        if not meeting.action_items or item_index >= len(meeting.action_items):
            return None

        action_items = list(meeting.action_items)
        action_items[item_index]["status"] = status

        meeting.action_items = action_items
        meeting.updated_at = utc_now()

        flag_modified(meeting, "action_items")

        self.db.commit()
        self.db.refresh(meeting)

        logger.info(f"Action item atualizado: reunião {meeting_id}, item {item_index}")
        return meeting

    def count_by_user(self, user_id: int) -> int:
        """Conta total de reuniões do usuário."""
        return self.db.query(func.count(Meeting.id)).filter(Meeting.user_id == user_id).scalar() or 0

    def get_action_items_pending(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Retorna todos os action items pendentes.

        Args:
            user_id: ID do usuário

        Returns:
            Lista de action items pendentes
        """
        meetings = self.db.query(Meeting).filter(Meeting.user_id == user_id).all()

        pending_items = []
        for meeting in meetings:
            if meeting.action_items:
                for idx, item in enumerate(meeting.action_items):
                    if item.get("status", "pending") == "pending":
                        pending_items.append(
                            {"meeting_id": meeting.id, "meeting_title": meeting.title, "item_index": idx, **item}
                        )

        return pending_items

"""
Serviço para gerenciamento de mensagens agendadas.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import Contact, ScheduledMessage, ScheduledMessageStatus

logger = logging.getLogger(__name__)


class ScheduledMessageService:
    """Serviço para gerenciamento de mensagens agendadas."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: int,
        message: str,
        scheduled_time: datetime,
        contact_id: Optional[int] = None,
        recipient_phone: Optional[str] = None,
        recipient_name: Optional[str] = None,
        group_name: Optional[str] = None,
    ) -> ScheduledMessage:
        """Cria uma nova mensagem agendada."""
        scheduled_msg = ScheduledMessage(
            user_id=user_id,
            contact_id=contact_id,
            recipient_phone=recipient_phone,
            recipient_name=recipient_name,
            group_name=group_name,
            message=message,
            scheduled_time=scheduled_time,
            status=ScheduledMessageStatus.PENDING,
        )
        self.db.add(scheduled_msg)
        self.db.commit()
        self.db.refresh(scheduled_msg)
        logger.info(f"Mensagem agendada criada: ID {scheduled_msg.id} para {scheduled_time}")
        return scheduled_msg

    def create_from_entities(self, user_id: int, data: Dict[str, Any]) -> ScheduledMessage:
        """Cria mensagem agendada a partir de entidades da IA."""
        from dateutil import parser

        message = data.get("message", "")
        scheduled_time_str = data.get("scheduled_time")
        recipient_name = data.get("recipient_name")
        recipient_phone = data.get("recipient_phone")
        group_name = data.get("group_name")
        contact_id = None

        # Parsear data/hora
        if isinstance(scheduled_time_str, str):
            scheduled_time = parser.parse(scheduled_time_str)
        elif isinstance(scheduled_time_str, datetime):
            scheduled_time = scheduled_time_str
        else:
            scheduled_time = datetime.now()

        # Se tiver nome do destinatário, buscar contato
        if recipient_name and not recipient_phone:
            contact = self._find_contact_by_name(user_id, recipient_name)
            if contact:
                contact_id = contact.id
                recipient_phone = contact.phone_number
                recipient_name = contact.name

        return self.create(
            user_id=user_id,
            message=message,
            scheduled_time=scheduled_time,
            contact_id=contact_id,
            recipient_phone=recipient_phone,
            recipient_name=recipient_name,
            group_name=group_name,
        )

    def _find_contact_by_name(self, user_id: int, name: str) -> Optional[Contact]:
        """Busca contato por nome."""
        return (
            self.db.query(Contact)
            .filter(
                and_(
                    Contact.user_id == user_id,
                    Contact.name.ilike(f"%{name}%"),
                    Contact.is_active == True,
                )
            )
            .first()
        )

    def get_pending(self, user_id: int) -> List[ScheduledMessage]:
        """Retorna mensagens pendentes do usuário."""
        return (
            self.db.query(ScheduledMessage)
            .filter(
                and_(
                    ScheduledMessage.user_id == user_id,
                    ScheduledMessage.status == ScheduledMessageStatus.PENDING,
                )
            )
            .order_by(ScheduledMessage.scheduled_time.asc())
            .all()
        )

    def get_due_messages(self) -> List[ScheduledMessage]:
        """Retorna mensagens que devem ser enviadas agora."""
        now = datetime.utcnow()
        return (
            self.db.query(ScheduledMessage)
            .filter(
                and_(
                    ScheduledMessage.status == ScheduledMessageStatus.PENDING,
                    ScheduledMessage.scheduled_time <= now,
                )
            )
            .all()
        )

    def mark_as_sent(self, message_id: int) -> bool:
        """Marca mensagem como enviada."""
        msg = self.db.query(ScheduledMessage).filter(ScheduledMessage.id == message_id).first()
        if msg:
            msg.status = ScheduledMessageStatus.SENT
            msg.sent_at = datetime.utcnow()
            self.db.commit()
            return True
        return False

    def mark_as_failed(self, message_id: int, error: str) -> bool:
        """Marca mensagem como falha."""
        msg = self.db.query(ScheduledMessage).filter(ScheduledMessage.id == message_id).first()
        if msg:
            msg.status = ScheduledMessageStatus.FAILED
            msg.error_message = error
            self.db.commit()
            return True
        return False

    def cancel(self, user_id: int, message_id: int) -> bool:
        """Cancela mensagem agendada."""
        msg = (
            self.db.query(ScheduledMessage)
            .filter(
                and_(
                    ScheduledMessage.id == message_id,
                    ScheduledMessage.user_id == user_id,
                    ScheduledMessage.status == ScheduledMessageStatus.PENDING,
                )
            )
            .first()
        )
        if msg:
            msg.status = ScheduledMessageStatus.CANCELLED
            self.db.commit()
            return True
        return False

    def list(self, user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista mensagens agendadas do usuário."""
        query = self.db.query(ScheduledMessage).filter(ScheduledMessage.user_id == user_id)

        if status:
            query = query.filter(ScheduledMessage.status == ScheduledMessageStatus(status))

        messages = query.order_by(ScheduledMessage.scheduled_time.desc()).limit(50).all()

        return [
            {
                "id": m.id,
                "message": m.message[:100] + "..." if len(m.message) > 100 else m.message,
                "recipient_name": m.recipient_name,
                "recipient_phone": m.recipient_phone,
                "group_name": m.group_name,
                "scheduled_time": m.scheduled_time.isoformat() if m.scheduled_time else None,
                "status": m.status.value,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            }
            for m in messages
        ]

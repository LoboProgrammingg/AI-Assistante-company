import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now():
    """Retorna datetime atual em UTC."""
    return datetime.now(timezone.utc)


from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import ConversationMemory, Message

logger = logging.getLogger(__name__)


class MemoryService:
    """Serviço para gerenciamento de memória do usuário."""

    def __init__(self, db: Session):
        self.db = db

    def get_memory(self, user_id: int, key: str) -> Optional[Dict[str, Any]]:
        """
        Recupera uma memória específica.

        Args:
            user_id: ID do usuário
            key: Chave da memória

        Returns:
            Valor da memória ou None
        """
        memory = (
            self.db.query(ConversationMemory)
            .filter(and_(ConversationMemory.user_id == user_id, ConversationMemory.key == key))
            .first()
        )

        if memory:
            memory.accessed_at = utc_now()
            self.db.commit()
            return memory.value

        return None

    def set_memory(self, user_id: int, key: str, value: Dict[str, Any]) -> ConversationMemory:
        """
        Define ou atualiza uma memória.

        Args:
            user_id: ID do usuário
            key: Chave da memória
            value: Valor a armazenar

        Returns:
            ConversationMemory criada/atualizada
        """
        memory = (
            self.db.query(ConversationMemory)
            .filter(and_(ConversationMemory.user_id == user_id, ConversationMemory.key == key))
            .first()
        )

        if memory:
            memory.value = value
            memory.updated_at = utc_now()
        else:
            memory = ConversationMemory(
                user_id=user_id,
                key=key,
                value=value,
            )
            self.db.add(memory)

        self.db.commit()
        self.db.refresh(memory)

        logger.debug(f"Memória salva: {key} para usuário {user_id}")
        return memory

    def delete_memory(self, user_id: int, key: str) -> bool:
        """Remove uma memória."""
        memory = (
            self.db.query(ConversationMemory)
            .filter(and_(ConversationMemory.user_id == user_id, ConversationMemory.key == key))
            .first()
        )

        if memory:
            self.db.delete(memory)
            self.db.commit()
            return True

        return False

    def get_conversation_context(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Recupera últimas mensagens para contexto expandido.

        Args:
            user_id: ID do usuário
            limit: Quantidade de mensagens (padrão aumentado para 20)

        Returns:
            Lista de mensagens formatadas com metadados
        """
        messages = (
            self.db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "role": "user" if m.direction == "incoming" else "assistant",
                "content": m.content or m.audio_transcription or "",
                "intent": m.intent,
                "entities": m.entities or {},
                "ai_response": m.ai_response,
                "timestamp": m.created_at.isoformat() if m.created_at else None,
            }
            for m in reversed(messages)
        ]

    def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """Recupera preferências aprendidas do usuário."""
        return self.get_memory(user_id, "preferences") or {}

    def update_user_preferences(self, user_id: int, updates: Dict[str, Any]) -> None:
        """Atualiza preferências do usuário."""
        prefs = self.get_user_preferences(user_id)
        prefs.update(updates)
        self.set_memory(user_id, "preferences", prefs)

    def get_learned_facts(self, user_id: int) -> Dict[str, Any]:
        """Recupera fatos aprendidos sobre o usuário."""
        return self.get_memory(user_id, "learned_facts") or {}

    def add_learned_fact(self, user_id: int, key: str, value: Any) -> None:
        """Adiciona novo fato aprendido."""
        facts = self.get_learned_facts(user_id)
        facts[key] = value
        self.set_memory(user_id, "learned_facts", facts)

    def get_interaction_stats(self, user_id: int) -> Dict[str, int]:
        """Recupera estatísticas de interação."""
        return self.get_memory(user_id, "interaction_stats") or {
            "total_messages": 0,
            "reminders_created": 0,
            "transactions_logged": 0,
            "meetings_analyzed": 0,
        }

    def increment_stat(self, user_id: int, stat_key: str) -> None:
        """Incrementa uma estatística."""
        stats = self.get_interaction_stats(user_id)
        stats[stat_key] = stats.get(stat_key, 0) + 1
        self.set_memory(user_id, "interaction_stats", stats)

    def get_full_context(self, user_id: int) -> Dict[str, Any]:
        """
        Retorna contexto completo para o agente.

        Args:
            user_id: ID do usuário

        Returns:
            Dict com todo o contexto
        """
        return {
            "conversation": self.get_conversation_context(user_id),
            "preferences": self.get_user_preferences(user_id),
            "facts": self.get_learned_facts(user_id),
            "stats": self.get_interaction_stats(user_id),
            "user_data": self.get_user_data_summary(user_id),
        }

    def get_user_data_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Retorna resumo dos dados do usuário (finanças, lembretes, reuniões, contatos).

        Args:
            user_id: ID do usuário

        Returns:
            Dict com resumo dos dados
        """
        from datetime import datetime, timedelta

        from sqlalchemy import and_, func

        from app.models import Contact, Document, Finance, Meeting, Reminder

        today = utc_now().date()
        month_start = today.replace(day=1)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)

        # Resumo financeiro do mês atual
        finances_this_month = (
            self.db.query(Finance)
            .filter(and_(Finance.user_id == user_id, Finance.transaction_date >= month_start))
            .all()
        )

        total_expense = sum(f.amount for f in finances_this_month if f.type and f.type.value == "expense")
        total_income = sum(f.amount for f in finances_this_month if f.type and f.type.value == "income")

        # Gastos por categoria
        expenses_by_category = {}
        for f in finances_this_month:
            if f.type and f.type.value == "expense":
                cat = f.category.name if f.category else "Outros"
                expenses_by_category[cat] = expenses_by_category.get(cat, 0) + f.amount

        # Finanças do mês passado para comparação
        finances_last_month = (
            self.db.query(Finance)
            .filter(
                and_(
                    Finance.user_id == user_id,
                    Finance.transaction_date >= last_month_start,
                    Finance.transaction_date < month_start,
                )
            )
            .all()
        )

        last_month_expense = sum(f.amount for f in finances_last_month if f.type and f.type.value == "expense")

        # Lembretes ativos
        active_reminders = (
            self.db.query(Reminder)
            .filter(and_(Reminder.user_id == user_id, Reminder.is_active == True, Reminder.is_completed == False))
            .order_by(Reminder.scheduled_time.asc())
            .limit(5)
            .all()
        )

        upcoming_reminders = [
            {
                "title": r.title,
                "scheduled_time": r.scheduled_time.strftime("%d/%m/%Y %H:%M") if r.scheduled_time else "",
                "remind_before": r.remind_before_minutes,
            }
            for r in active_reminders
        ]

        # Últimas reuniões
        recent_meetings = (
            self.db.query(Meeting).filter(Meeting.user_id == user_id).order_by(Meeting.created_at.desc()).limit(3).all()
        )

        meetings_summary = [
            {
                "title": m.title or "Reunião",
                "date": m.date.strftime("%d/%m/%Y") if m.date else "",
                "summary": (m.summary[:100] + "...") if m.summary and len(m.summary) > 100 else m.summary,
            }
            for m in recent_meetings
        ]

        # Contatos do usuário
        contacts = (
            self.db.query(Contact)
            .filter(and_(Contact.user_id == user_id, Contact.is_active == True))
            .order_by(Contact.group_name.asc(), Contact.name.asc())
            .all()
        )

        # Agrupar contatos por grupo
        contacts_by_group = {}
        for c in contacts:
            group = c.group_name or "outros"
            if group not in contacts_by_group:
                contacts_by_group[group] = []
            contacts_by_group[group].append({"name": c.name, "phone": c.phone_number})

        contacts_summary = {
            "total": len(contacts),
            "by_group": contacts_by_group,
            "groups": list(contacts_by_group.keys()),
        }

        return {
            "finances": {
                "this_month": {
                    "total_expense": total_expense,
                    "total_income": total_income,
                    "balance": total_income - total_expense,
                    "by_category": expenses_by_category,
                },
                "last_month_expense": last_month_expense,
                "expense_change": total_expense - last_month_expense if last_month_expense > 0 else 0,
            },
            "reminders": {"active_count": len(active_reminders), "upcoming": upcoming_reminders},
            "meetings": {"recent": meetings_summary},
            "contacts": contacts_summary,
            "documents": self._get_documents_summary(user_id, Document),
        }

    def _get_documents_summary(self, user_id: int, Document) -> Dict[str, Any]:
        """Retorna resumo dos documentos do usuário para contexto da IA."""
        from sqlalchemy import and_

        # Buscar documentos marcados para IA
        ai_documents = (
            self.db.query(Document)
            .filter(and_(Document.user_id == user_id, Document.send_to_ai == True, Document.is_active == True))
            .order_by(Document.created_at.desc())
            .all()
        )

        documents_content = []
        for doc in ai_documents:
            doc_info = {
                "title": doc.title or doc.original_filename,
                "category": doc.category.value if doc.category else "other",
                "content_preview": (
                    (doc.content_text[:500] + "...")
                    if doc.content_text and len(doc.content_text) > 500
                    else doc.content_text
                ),
            }
            documents_content.append(doc_info)

        return {"count": len(ai_documents), "documents": documents_content}

    def update_after_action(self, user_id: int, action: str, entities: Dict[str, Any]) -> None:
        """
        Atualiza memória após uma ação.

        Args:
            user_id: ID do usuário
            action: Ação executada
            entities: Entidades processadas
        """
        self.increment_stat(user_id, "total_messages")

        if action == "create_reminder":
            self.increment_stat(user_id, "reminders_created")
        elif action == "create_finance":
            self.increment_stat(user_id, "transactions_logged")
        elif action == "create_meeting":
            self.increment_stat(user_id, "meetings_analyzed")

    def clear_user_memory(self, user_id: int) -> int:
        """
        Limpa toda a memória de um usuário.

        Args:
            user_id: ID do usuário

        Returns:
            Quantidade de registros removidos
        """
        deleted = self.db.query(ConversationMemory).filter(ConversationMemory.user_id == user_id).delete()

        self.db.commit()
        logger.info(f"Memória limpa para usuário {user_id}: {deleted} registros")

        return deleted

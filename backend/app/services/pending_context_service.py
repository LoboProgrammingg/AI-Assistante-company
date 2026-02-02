"""
PendingContextService - Gerencia contexto pendente entre mensagens.

Quando a IA faz uma pergunta ao usuário (ex: "qual o valor?"), 
este serviço guarda o contexto para que a próxima mensagem seja
interpretada corretamente.

Exemplo:
1. User: "anota um uber"
2. IA: "qual foi o valor?"
3. Pending: {action: "create_finance", category: "transporte", description: "uber", awaiting: "amount"}
4. User: "40 reais"
5. Sistema detecta pending, combina com "40 reais" e executa a ação
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


class PendingContextService:
    """
    Gerencia contexto pendente de ações entre mensagens.
    
    Armazena na tabela user_memories com memory_type='pending_action'.
    TTL de 10 minutos (conversas devem ser rápidas).
    """

    PENDING_TTL_MINUTES = 10
    PENDING_KEY = "pending_action"

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_pending_context(self) -> Optional[Dict[str, Any]]:
        """
        Busca contexto pendente ativo para o usuário.
        
        Returns:
            Dict com contexto pendente ou None se não houver
        """
        try:
            from app.models.user_memory import MemoryTypeEnum, UserMemory

            cutoff = utc_now() - timedelta(minutes=self.PENDING_TTL_MINUTES)

            pending = (
                self.db.query(UserMemory)
                .filter(
                    and_(
                        UserMemory.user_id == self.user_id,
                        UserMemory.key == self.PENDING_KEY,
                        UserMemory.is_archived == False,
                        UserMemory.created_at >= cutoff,
                    )
                )
                .order_by(desc(UserMemory.created_at))
                .first()
            )

            if pending and pending.value:
                value = pending.value
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass
                
                logger.info(f"[PENDING] Found pending context: {value}")
                return value

            return None

        except Exception as e:
            logger.error(f"[PENDING] Error getting pending context: {e}")
            return None

    def set_pending_context(
        self,
        action_type: str,
        partial_data: Dict[str, Any],
        awaiting_field: str,
        question_asked: str,
    ) -> bool:
        """
        Define contexto pendente para aguardar resposta do usuário.
        
        Args:
            action_type: Tipo de ação (ex: "create_finance")
            partial_data: Dados já coletados (ex: {"category": "transporte", "description": "uber"})
            awaiting_field: Campo que está faltando (ex: "amount")
            question_asked: Pergunta feita ao usuário (ex: "Qual foi o valor?")
            
        Returns:
            True se salvou com sucesso
        """
        try:
            from app.models.user_memory import (
                ImportanceEnum,
                MemoryLayerEnum,
                MemorySourceEnum,
                MemoryTypeEnum,
                UserMemory,
            )

            # Limpar pendentes antigos
            self.clear_pending_context()

            pending_data = {
                "action_type": action_type,
                "partial_data": partial_data,
                "awaiting_field": awaiting_field,
                "question_asked": question_asked,
                "created_at": utc_now().isoformat(),
            }

            new_pending = UserMemory(
                user_id=self.user_id,
                memory_type=MemoryTypeEnum.ACTION,
                layer=MemoryLayerEnum.WORKING,
                category="pending",
                key=self.PENDING_KEY,
                value=pending_data,
                summary=f"Aguardando {awaiting_field} para {action_type}",
                confidence=1.0,
                importance=ImportanceEnum.HIGH,
                source=MemorySourceEnum.SYSTEM,
                created_at=utc_now(),
                updated_at=utc_now(),
            )

            self.db.add(new_pending)
            self.db.commit()

            logger.info(
                f"[PENDING] Set pending context: {action_type} awaiting {awaiting_field}"
            )
            return True

        except Exception as e:
            logger.error(f"[PENDING] Error setting pending context: {e}")
            self.db.rollback()
            return False

    def clear_pending_context(self) -> bool:
        """Limpa contexto pendente do usuário."""
        try:
            from app.models.user_memory import UserMemory

            self.db.query(UserMemory).filter(
                and_(
                    UserMemory.user_id == self.user_id,
                    UserMemory.key == self.PENDING_KEY,
                )
            ).delete()

            self.db.commit()
            logger.debug(f"[PENDING] Cleared pending context for user {self.user_id}")
            return True

        except Exception as e:
            logger.error(f"[PENDING] Error clearing pending context: {e}")
            self.db.rollback()
            return False

    def resolve_pending_context(
        self, user_response: str
    ) -> Optional[Dict[str, Any]]:
        """
        Tenta resolver contexto pendente com a resposta do usuário.
        
        Args:
            user_response: Mensagem do usuário (ex: "40 reais")
            
        Returns:
            Dict com ação completa se resolvido, None caso contrário
        """
        pending = self.get_pending_context()
        if not pending:
            return None

        action_type = pending.get("action_type")
        partial_data = pending.get("partial_data", {})
        awaiting_field = pending.get("awaiting_field")

        if not awaiting_field:
            return None

        # Extrair valor da resposta
        extracted_value = self._extract_value(user_response, awaiting_field)
        
        if extracted_value is not None:
            # Combinar dados
            complete_data = {**partial_data, awaiting_field: extracted_value}
            
            # Limpar pendente
            self.clear_pending_context()
            
            logger.info(
                f"[PENDING] Resolved: {action_type} with {awaiting_field}={extracted_value}"
            )
            
            return {
                "action_type": action_type,
                "params": complete_data,
                "resolved_from_pending": True,
            }

        return None

    def _extract_value(self, text: str, field_type: str) -> Optional[Any]:
        """
        Extrai valor da resposta do usuário baseado no tipo de campo.
        
        Args:
            text: Texto do usuário
            field_type: Tipo de campo esperado (amount, date, description, etc)
            
        Returns:
            Valor extraído ou None
        """
        import re

        text_lower = text.lower().strip()

        if field_type == "amount":
            # Extrair valor monetário
            # Padrões: "40", "40 reais", "R$ 40", "40,50", "R$40.00"
            patterns = [
                r"r?\$?\s*(\d+(?:[.,]\d{1,2})?)",
                r"(\d+(?:[.,]\d{1,2})?)\s*(?:reais|real|r\$)?",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    value_str = match.group(1).replace(",", ".")
                    try:
                        return float(value_str)
                    except ValueError:
                        continue

        elif field_type == "description":
            # Usar texto como descrição
            return text.strip()

        elif field_type == "date":
            # Detectar datas relativas
            if "hoje" in text_lower:
                return utc_now().strftime("%Y-%m-%d")
            elif "ontem" in text_lower:
                return (utc_now() - timedelta(days=1)).strftime("%Y-%m-%d")
            # TODO: Adicionar mais padrões de data

        elif field_type == "category":
            # Categorias de finanças
            category_map = {
                "uber": "transporte",
                "99": "transporte",
                "taxi": "transporte",
                "onibus": "transporte",
                "comida": "alimentacao",
                "restaurante": "alimentacao",
                "mercado": "alimentacao",
                "supermercado": "alimentacao",
                "ifood": "alimentacao",
                "luz": "contas",
                "agua": "contas",
                "internet": "contas",
                "aluguel": "moradia",
            }
            
            for keyword, category in category_map.items():
                if keyword in text_lower:
                    return category

        return None


def get_pending_context_service(db: Session, user_id: int) -> PendingContextService:
    """Factory function para criar serviço de contexto pendente."""
    return PendingContextService(db, user_id)

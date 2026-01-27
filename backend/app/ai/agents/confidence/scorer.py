"""
Confidence Scorer - Avaliação de confiança para ações.

Regras:
- Score ALTO (>= 0.9): Ação automática permitida
- Score MÉDIO (0.5 - 0.9): Requer confirmação do usuário
- Score BAIXO (< 0.5): Apenas sugestão, não executa

Ações críticas:
- Financeiras: sempre requerem score alto
- Mensagens externas: sempre confirmação
- Deleções: sempre confirmação
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceResult:
    """Resultado da avaliação de confiança."""

    score: float
    can_auto_execute: bool
    requires_confirmation: bool
    only_suggest: bool
    reasons: List[str]

    @property
    def level(self) -> str:
        if self.score >= 0.9:
            return "high"
        elif self.score >= 0.5:
            return "medium"
        return "low"


class ConfidenceScorer:
    """Sistema de scoring de confiança para ações."""

    # Ações que SEMPRE requerem confirmação, independente do score
    ALWAYS_CONFIRM = {
        "schedule_message",
        "delete_finance",
        "delete_reminder",
        "delete_task",
        "send_email",
        "make_payment",
        "cancel_subscription",
    }

    # Ações que NUNCA podem ser auto-executadas
    NEVER_AUTO = {
        "make_payment",
        "cancel_subscription",
        "delete_all",
        "send_to_external",
    }

    # Multiplicadores por tipo de ação
    ACTION_MULTIPLIERS = {
        # Ações de leitura - baixo risco
        "query_finance": 1.2,
        "list_reminders": 1.2,
        "list_tasks": 1.2,
        "list_events": 1.2,
        # Ações de criação - risco médio
        "create_finance": 0.9,
        "create_reminder": 1.0,
        "create_task": 1.0,
        # Ações de modificação - risco alto
        "update_finance": 0.8,
        "update_reminder": 0.9,
        "delete_finance": 0.6,
        "delete_reminder": 0.7,
        # Ações externas - risco muito alto
        "schedule_message": 0.5,
        "create_event": 0.8,
    }

    # Campos que aumentam confiança quando presentes
    CONFIDENCE_BOOSTERS = {
        "amount": 0.1,
        "description": 0.05,
        "due_date": 0.1,
        "vendor": 0.1,
        "title": 0.05,
        "scheduled_time": 0.1,
    }

    # Campos obrigatórios por ação
    REQUIRED_FIELDS = {
        "create_finance": ["amount"],
        "create_reminder": ["title", "scheduled_time"],
        "create_task": ["title"],
        "schedule_message": ["message", "recipient", "scheduled_time"],
        "create_event": ["title", "start_time"],
    }

    @classmethod
    def calculate(
        cls,
        action: str,
        data: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> ConfidenceResult:
        """
        Calcula score de confiança para uma ação.

        Args:
            action: Tipo da ação
            data: Dados extraídos
            context: Contexto adicional (histórico, preferências)

        Returns:
            ConfidenceResult com score e recomendações
        """
        context = context or {}
        reasons = []

        # 1. Score base pela completude dos dados
        required = cls.REQUIRED_FIELDS.get(action, [])
        if required:
            present = sum(1 for f in required if data.get(f))
            base_score = present / len(required)
            reasons.append(f"{present}/{len(required)} campos obrigatórios")
        else:
            base_score = 0.7
            reasons.append("Ação sem campos obrigatórios")

        # 2. Boost por campos adicionais
        for field, boost in cls.CONFIDENCE_BOOSTERS.items():
            if data.get(field) and field not in required:
                base_score = min(1.0, base_score + boost)

        # 3. Multiplicador por tipo de ação
        multiplier = cls.ACTION_MULTIPLIERS.get(action, 1.0)
        score = min(1.0, base_score * multiplier)

        if multiplier < 1.0:
            reasons.append(f"Ação de risco ({action})")

        # 4. Penalidades específicas
        score = cls._apply_penalties(score, action, data, reasons)

        # 5. Bonus por contexto
        score = cls._apply_context_bonus(score, context, reasons)

        # 6. Determinar comportamento
        can_auto = score >= 0.9 and action not in cls.NEVER_AUTO
        requires_confirm = action in cls.ALWAYS_CONFIRM or (0.5 <= score < 0.9 and action not in cls.NEVER_AUTO)
        only_suggest = score < 0.5 or action in cls.NEVER_AUTO

        if action in cls.ALWAYS_CONFIRM:
            can_auto = False
            requires_confirm = True
            reasons.append("Ação requer confirmação obrigatória")

        if action in cls.NEVER_AUTO:
            can_auto = False
            only_suggest = True
            reasons.append("Ação nunca é automática")

        result = ConfidenceResult(
            score=round(score, 2),
            can_auto_execute=can_auto,
            requires_confirmation=requires_confirm,
            only_suggest=only_suggest,
            reasons=reasons,
        )

        logger.info(f"[CONFIDENCE] {action}: {score:.0%} | " f"Auto: {can_auto} | Confirm: {requires_confirm}")

        return result

    @classmethod
    def _apply_penalties(
        cls,
        score: float,
        action: str,
        data: Dict[str, Any],
        reasons: List[str],
    ) -> float:
        """Aplica penalidades ao score."""
        # Valores financeiros altos
        amount = data.get("amount", 0)
        if amount > 5000:
            score = max(0.3, score - 0.2)
            reasons.append(f"Valor alto: R$ {amount:,.2f}")
        elif amount > 1000:
            score = max(0.5, score - 0.1)
            reasons.append(f"Valor moderado: R$ {amount:,.2f}")

        # Datas no passado
        date_str = data.get("due_date") or data.get("scheduled_time") or ""
        if date_str:
            from datetime import datetime

            try:
                date = datetime.strptime(date_str[:10], "%Y-%m-%d")
                if date.date() < datetime.now().date():
                    score = max(0.3, score - 0.3)
                    reasons.append("Data no passado")
            except ValueError:
                pass

        # Mensagens para múltiplos destinatários
        recipients = data.get("recipients", [])
        if len(recipients) > 1:
            score = max(0.4, score - 0.2)
            reasons.append(f"Múltiplos destinatários: {len(recipients)}")

        return score

    @classmethod
    def _apply_context_bonus(
        cls,
        score: float,
        context: Dict[str, Any],
        reasons: List[str],
    ) -> float:
        """Aplica bonus por contexto histórico."""
        # Ação similar ao histórico recente
        if context.get("similar_recent_action"):
            score = min(1.0, score + 0.1)
            reasons.append("Ação similar ao histórico")

        # Usuário tem preferência configurada
        if context.get("user_preference_auto"):
            score = min(1.0, score + 0.05)

        # Horário comercial normal
        if context.get("business_hours"):
            score = min(1.0, score + 0.05)

        return score


def calculate_action_confidence(
    action: str,
    data: Dict[str, Any],
    context: Dict[str, Any] = None,
) -> ConfidenceResult:
    """Atalho para calcular confiança."""
    return ConfidenceScorer.calculate(action, data, context)


def requires_confirmation(action: str, data: Dict[str, Any]) -> bool:
    """Verifica se ação requer confirmação."""
    result = ConfidenceScorer.calculate(action, data)
    return result.requires_confirmation or result.only_suggest

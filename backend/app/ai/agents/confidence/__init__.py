"""
Confidence Scoring - Sistema de avaliação de confiança para ações.

Responsabilidades:
- Avaliar confiança de qualquer ação sugerida
- Definir se a IA pode agir ou deve confirmar
- Reduzir erros críticos
"""

from app.ai.agents.confidence.scorer import (
    ConfidenceScorer,
    calculate_action_confidence,
    requires_confirmation,
)

__all__ = [
    "ConfidenceScorer",
    "calculate_action_confidence",
    "requires_confirmation",
]

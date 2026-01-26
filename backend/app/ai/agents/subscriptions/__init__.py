"""
Subscriptions Agent - Gerenciamento de assinaturas e cobranças recorrentes.

Responsabilidades:
- Identificar cobranças recorrentes
- Alertar sobre aumentos de preço
- Sugerir cancelamento de serviços não utilizados

Regras:
- Nunca cancelar automaticamente
- Sempre pedir confirmação
- Priorizar impacto financeiro
"""

from app.ai.agents.subscriptions.agent import SubscriptionsAgent

__all__ = ["SubscriptionsAgent"]

"""
Patterns Agent - Detecção de padrões e anomalias.

Responsabilidades:
- Analisar histórico financeiro, agenda e comportamento
- Detectar desvios, excessos e padrões recorrentes
- Gerar alertas inteligentes

Regras:
- Nunca emitir julgamentos
- Sempre explicar o motivo do alerta
- Alertas informativos, não invasivos
"""

from app.ai.agents.patterns.agent import PatternsAgent

__all__ = ["PatternsAgent"]

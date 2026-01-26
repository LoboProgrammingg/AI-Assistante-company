"""
Memory Agent - Agente de memória de longo prazo.

Responsabilidades:
- Detectar informações pessoais relevantes
- Decidir o que deve ser salvo como memória
- Atualizar preferências do usuário

Regras:
- NÃO salvar tudo
- Priorizar: hábitos, preferências, recorrências, aversões
- Nunca salvar dados sensíveis sem confirmação
"""

from app.ai.agents.memory.agent import MemoryAgent

__all__ = ["MemoryAgent"]

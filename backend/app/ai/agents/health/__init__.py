"""
Health Agent - Organização de saúde (LEVE).

Responsabilidades:
- Organizar compromissos de saúde
- Criar lembretes de remédios e consultas
- Armazenar histórico organizacional (não clínico)

RESTRIÇÕES CRÍTICAS:
- ❌ NÃO diagnosticar
- ❌ NÃO sugerir tratamentos
- ❌ NÃO interpretar exames
"""

from app.ai.agents.health.agent import HealthAgent

__all__ = ["HealthAgent"]
